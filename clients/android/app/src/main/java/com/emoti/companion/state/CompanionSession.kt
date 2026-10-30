package com.emoti.companion.state

import com.emoti.companion.data.CancelRequest
import com.emoti.companion.data.ContextVersion
import com.emoti.companion.data.HostApi
import com.emoti.companion.data.HostException
import com.emoti.companion.data.HostUnreachableException
import com.emoti.companion.data.MemoryAlbum
import com.emoti.companion.data.MemoryRequest
import com.emoti.companion.data.MemoryResponse
import com.emoti.companion.data.MemorySource
import com.emoti.companion.data.MessageRequest
import com.emoti.companion.data.MessageResult
import com.emoti.companion.data.Capabilities
import com.emoti.companion.data.StoredPairing
import com.emoti.companion.data.version
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.UUID

enum class Phase { Unpaired, Pairing, Connecting, Online, Offline, Unauthorized }

enum class Role { User, Companion, System }

/** Delivery states are kept distinct so an unanswered write is never shown as sent or failed. */
enum class LineStatus { Delivering, DeliveryUnknown, Running, Completed, Cancelled, Stale, Rejected }

data class ChatLine(
    val id: String,
    val role: Role,
    val text: String,
    val status: LineStatus = LineStatus.Completed,
    val requestId: String? = null,
    val note: String? = null,
)

data class UiState(
    val phase: Phase = Phase.Unpaired,
    val hostUrl: String = "",
    val characterId: String = "",
    val capabilities: Capabilities = Capabilities(),
    val version: ContextVersion? = null,
    val messages: List<ChatLine> = emptyList(),
    val album: MemoryAlbum? = null,
    val replyRequestId: String? = null,
    val notice: String? = null,
    val error: String? = null,
)

interface PairingStore {
    fun load(): StoredPairing?
    fun save(pairing: StoredPairing)
    fun clear()
}

/**
 * Phone-side session against the desktop host. The host stays authoritative: every write echoes the
 * last seen version, and any version change drops cached chat, album and in-flight replies.
 */
class CompanionSession(
    private val store: PairingStore,
    private val apiFactory: (String) -> HostApi = { HostApi(it) },
    private val pollIntervalMs: Long = 500,
    private val maxReplyPolls: Int = 240,
) {
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()
    private var api: HostApi? = null
    private var eventCursor = 0
    private val lock = Mutex()

    fun restore(): Boolean {
        val pairing = store.load() ?: return false
        api = apiFactory(pairing.hostUrl).withToken(pairing.token)
        _state.update { it.copy(phase = Phase.Connecting, hostUrl = pairing.hostUrl) }
        return true
    }

    suspend fun pair(hostUrl: String, invitation: String, deviceName: String) {
        _state.update { it.copy(phase = Phase.Pairing, error = null) }
        val base = try {
            apiFactory(hostUrl)
        } catch (exc: IllegalArgumentException) {
            _state.update { it.copy(phase = Phase.Unpaired, error = exc.message) }
            return
        }
        try {
            val paired = base.pair(invitation, deviceName)
            val url = base.base.toString()
            store.save(StoredPairing(url, paired.deviceId, paired.accessToken, paired.expiresAt))
            api = base.withToken(paired.accessToken)
            _state.value = UiState(phase = Phase.Connecting, hostUrl = url)
            refresh()
        } catch (exc: HostException) {
            _state.update { it.copy(phase = Phase.Unpaired, error = errorText(exc)) }
        } catch (exc: HostUnreachableException) {
            _state.update { it.copy(phase = Phase.Unpaired, error = "连不上电脑：请确认桌面端已开启手机连接，地址正确。") }
        }
    }

    fun unpair() {
        store.clear()
        api = null
        eventCursor = 0
        _state.value = UiState()
    }

    /** Reads session first, then content, so stale cache is cleared before anything is shown again. */
    suspend fun refresh() = guarded {
        val session = it.session()
        adopt(session.version(), session.capabilities)
        eventCursor = maxOf(eventCursor, session.revision)
        val memory = it.memory()
        if (adopt(memory.version())) {
            return@guarded
        }
        _state.update { s -> s.copy(album = memory.album, phase = Phase.Online) }
    }

    suspend fun pollEvents() = guarded {
        val events = it.events(eventCursor)
        val invalidated = events.resyncRequired || events.events.any { e -> e.clearCachedContent }
        events.events.maxOfOrNull { e -> e.sequence }?.let { seq -> eventCursor = maxOf(eventCursor, seq) }
        val changed = adopt(ContextVersion(events.sessionId, events.revision, events.characterId, events.contextEpoch))
        if (invalidated && !changed) clearCache("电脑端的回忆或上下文已更新，旧内容已清除。")
        if (events.resyncRequired) eventCursor = events.revision
        if (invalidated || changed) {
            val memory = it.memory()
            if (!adopt(memory.version())) _state.update { s -> s.copy(album = memory.album) }
        }
        _state.update { s -> if (s.phase == Phase.Offline || s.phase == Phase.Connecting) s.copy(phase = Phase.Online) else s }
    }

    suspend fun send(text: String) {
        val clean = text.trim()
        if (clean.isEmpty() || _state.value.replyRequestId != null) return
        val requestId = "m-" + UUID.randomUUID()
        _state.update { it.copy(messages = it.messages + ChatLine(requestId, Role.User, clean, LineStatus.Delivering, requestId)) }
        deliver(requestId, clean)
    }

    /** Re-sends with the same request id; the host de-duplicates within the same session. */
    suspend fun retry(lineId: String) {
        val line = _state.value.messages.firstOrNull { it.id == lineId && it.status == LineStatus.DeliveryUnknown } ?: return
        setLine(lineId) { it.copy(status = LineStatus.Delivering, note = null) }
        deliver(line.requestId!!, line.text)
    }

    private suspend fun deliver(requestId: String, text: String) {
        val client = api ?: return
        val version = _state.value.version ?: return
        val first = try {
            client.sendMessage(MessageRequest(version.sessionId, version.contextEpoch, version.revision, requestId, text))
        } catch (exc: HostUnreachableException) {
            setLine(requestId) { it.copy(status = LineStatus.DeliveryUnknown, note = "不确定电脑是否收到，可以重试") }
            _state.update { it.copy(phase = Phase.Offline) }
            return
        } catch (exc: HostException) {
            rejectLine(requestId, exc)
            return
        }
        _state.update { it.copy(replyRequestId = requestId) }
        setLine(requestId) { it.copy(status = LineStatus.Running) }
        var result: MessageResult = first
        var polls = 0
        while (result.status == "running" && polls < maxReplyPolls) {
            delay(pollIntervalMs)
            polls++
            result = try {
                client.messageResult(requestId)
            } catch (exc: HostUnreachableException) {
                _state.update { it.copy(phase = Phase.Offline) }
                continue
            } catch (exc: HostException) {
                if (exc.status == 401) return unauthorized()
                rejectLine(requestId, exc)
                _state.update { it.copy(replyRequestId = null) }
                return
            }
        }
        applyResult(requestId, result)
    }

    private fun applyResult(requestId: String, result: MessageResult) {
        if (_state.value.messages.none { it.id == requestId }) {
            _state.update { it.copy(replyRequestId = null) }
            return
        }
        val current = _state.value.version
        val sameContext = result.sessionId == null || (current != null && result.sessionId == current.sessionId &&
            result.revision == current.revision && result.contextEpoch == current.contextEpoch &&
            result.characterId == current.characterId)
        when {
            result.status == "completed" && sameContext -> {
                val replies = result.events.filter { it.type == "speech" && it.speech.isNotBlank() }.mapIndexed { i, e ->
                    ChatLine("$requestId-r$i", Role.Companion, e.speech, LineStatus.Completed, requestId,
                        if (result.expressionMode == "local") "本地回应" else null)
                }
                _state.update { s ->
                    s.copy(messages = s.messages.map { if (it.id == requestId) it.copy(status = LineStatus.Completed) else it } + replies,
                        replyRequestId = null)
                }
            }
            result.status == "cancelled" -> {
                setLine(requestId) { it.copy(status = LineStatus.Cancelled, note = "已取消，电脑端不会发布这条回复") }
                _state.update { it.copy(replyRequestId = null) }
            }
            result.status == "running" -> {
                setLine(requestId) { it.copy(status = LineStatus.DeliveryUnknown, note = "回复时间过长，可稍后刷新") }
                _state.update { it.copy(replyRequestId = null) }
            }
            else -> {
                setLine(requestId) { it.copy(status = LineStatus.Stale, note = "上下文已变化，这条回复已作废") }
                _state.update { it.copy(replyRequestId = null) }
            }
        }
    }

    suspend fun cancelReply() {
        val requestId = _state.value.replyRequestId ?: return
        val version = _state.value.version ?: return
        guarded {
            it.cancel(CancelRequest(version.sessionId, version.contextEpoch, version.revision, requestId))
        }
    }

    suspend fun remember(text: String) = editMemory(MemoryRequest("", 0, 0, "", "remember", text = text.trim()))

    suspend fun confirm(pendingId: String) = editMemory(MemoryRequest("", 0, 0, "", "confirm", pendingId = pendingId))

    suspend fun correct(memoryId: String, title: String, text: String) =
        editMemory(MemoryRequest("", 0, 0, "", "correct", text = text.trim(), title = title.trim(), memoryId = memoryId))

    suspend fun forget(memoryId: String) = editMemory(MemoryRequest("", 0, 0, "", "forget", memoryId = memoryId))

    suspend fun source(memoryId: String): MemorySource? {
        var found: MemorySource? = null
        guarded { found = it.source(memoryId).source }
        return found
    }

    private suspend fun editMemory(template: MemoryRequest) {
        val version = _state.value.version ?: return
        val request = template.copy(sessionId = version.sessionId, expectedEpoch = version.contextEpoch,
            expectedRevision = version.revision, requestId = "e-" + UUID.randomUUID())
        guarded {
            val response = it.editMemory(request)
            adopt(response.version(), clearMessage = "回忆已更新，旧聊天内容已按电脑端要求清除。")
            _state.update { s -> s.copy(album = response.album, notice = noticeFor(request.operation)) }
        }
    }

    fun dismissNotice() = _state.update { it.copy(notice = null, error = null) }

    private suspend fun guarded(block: suspend (HostApi) -> Unit) {
        val client = api ?: return
        lock.withLock {
            try {
                block(client)
                _state.update { if (it.phase != Phase.Online) it.copy(phase = Phase.Online) else it }
            } catch (exc: HostUnreachableException) {
                _state.update { it.copy(phase = Phase.Offline) }
            } catch (exc: HostException) {
                when {
                    exc.status == 401 -> unauthorized()
                    exc.code == "stale_context" || exc.code == "session_changed" -> {
                        clearCache("电脑端状态已变化，这次操作没有执行。已刷新，请再试一次。")
                        val session = client.session()
                        adopt(session.version(), session.capabilities)
                        eventCursor = session.revision
                        val memory = client.memory()
                        if (!adopt(memory.version())) _state.update { it.copy(album = memory.album) }
                    }
                    else -> _state.update { it.copy(error = errorText(exc)) }
                }
            }
        }
    }

    /** Returns true when the version changed and cached content was dropped. */
    private fun adopt(next: ContextVersion, capabilities: Capabilities? = null,
                      clearMessage: String = "电脑端的回忆或角色已变化，旧内容已清除。"): Boolean {
        val previous = _state.value.version
        val changed = previous != null && previous != next
        if (changed) clearCache(clearMessage)
        _state.update {
            it.copy(version = next, characterId = next.characterId,
                capabilities = capabilities ?: it.capabilities)
        }
        return changed
    }

    private fun clearCache(message: String) {
        _state.update { it.copy(messages = emptyList(), album = null, replyRequestId = null, notice = message) }
    }

    private fun unauthorized() {
        store.clear()
        api = null
        _state.value = UiState(phase = Phase.Unauthorized, error = "这台手机的配对已撤销或过期，请在电脑上生成新的邀请码重新配对。")
    }

    private fun setLine(id: String, change: (ChatLine) -> ChatLine) =
        _state.update { s -> s.copy(messages = s.messages.map { if (it.id == id) change(it) else it }) }

    private fun rejectLine(id: String, exc: HostException) {
        if (exc.status == 401) return unauthorized()
        if (exc.code == "stale_context" || exc.code == "session_changed") {
            setLine(id) { it.copy(status = LineStatus.Stale, note = "电脑端状态已变化，这条没有发送") }
        } else {
            setLine(id) { it.copy(status = LineStatus.Rejected, note = errorText(exc)) }
        }
    }

    private fun noticeFor(operation: String) = when (operation) {
        "remember" -> "已经记下了。"
        "confirm" -> "已确认记住。"
        "correct" -> "已纠正，旧说法不会再被使用。"
        "forget" -> "已经忘记这件事。"
        else -> null
    }

    companion object {
        fun errorText(exc: HostException): String = when (exc.code) {
            "invalid_invitation" -> "邀请码无效、已过期或已被使用，请在电脑上重新生成。"
            "unauthorized" -> "配对已失效，请重新配对。"
            "character_forbidden" -> "电脑当前角色不是这台手机配对的角色。"
            "session_busy" -> "她还在回复上一句，请稍等。"
            "request_conflict" -> "请求编号冲突，请重新发送。"
            "session_capacity" -> "本次电脑会话请求过多，请重启电脑端连接。"
            "invalid_request" -> "内容过长或格式不正确（聊天和回忆最多 240 字）。"
            "host_closed" -> "电脑端已关闭手机连接。"
            "not_found", "request_not_found" -> "这条记录已经不存在。"
            else -> "电脑拒绝了这次操作（${exc.code}）。"
        }
    }
}

private fun MemoryResponse.version() = ContextVersion(sessionId, revision, characterId, contextEpoch)
