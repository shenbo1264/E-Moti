package com.emoti.companion.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// Field names follow the host contract in docs/handoff/20261029/host-integration.md.

@Serializable
data class PairRequest(val invitation: String, @SerialName("device_name") val deviceName: String)

@Serializable
data class PairResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("token_type") val tokenType: String,
    @SerialName("device_id") val deviceId: String,
    @SerialName("expires_at") val expiresAt: Double,
)

@Serializable
data class Capabilities(
    val chat: Boolean = false,
    val memory: Boolean = false,
    val observations: Boolean = false,
    val relay: Boolean = false,
    @SerialName("network_model_cancel") val networkModelCancel: Boolean = false,
)

@Serializable
data class SessionInfo(
    @SerialName("session_id") val sessionId: String,
    val revision: Int,
    @SerialName("character_id") val characterId: String,
    @SerialName("context_epoch") val contextEpoch: Int,
    val capabilities: Capabilities = Capabilities(),
)

/** The four values every write must echo; any change means cached content is no longer valid. */
data class ContextVersion(
    val sessionId: String,
    val revision: Int,
    val characterId: String,
    val contextEpoch: Int,
)

fun SessionInfo.version() = ContextVersion(sessionId, revision, characterId, contextEpoch)

@Serializable
data class MessageRequest(
    @SerialName("session_id") val sessionId: String,
    @SerialName("expected_epoch") val expectedEpoch: Int,
    @SerialName("expected_revision") val expectedRevision: Int,
    @SerialName("request_id") val requestId: String,
    val text: String,
)

@Serializable
data class CancelRequest(
    @SerialName("session_id") val sessionId: String,
    @SerialName("expected_epoch") val expectedEpoch: Int,
    @SerialName("expected_revision") val expectedRevision: Int,
    @SerialName("request_id") val requestId: String,
)

@Serializable
data class MemoryRequest(
    @SerialName("session_id") val sessionId: String,
    @SerialName("expected_epoch") val expectedEpoch: Int,
    @SerialName("expected_revision") val expectedRevision: Int,
    @SerialName("request_id") val requestId: String,
    val operation: String,
    val text: String = "",
    val title: String = "",
    @SerialName("memory_id") val memoryId: String = "",
    @SerialName("pending_id") val pendingId: String = "",
)

@Serializable
data class CompanionEvent(
    val type: String,
    @SerialName("character_name") val characterName: String = "",
    val speech: String = "",
    val payload: JsonObject = JsonObject(emptyMap()),
)

@Serializable
data class MessageResult(
    @SerialName("request_id") val requestId: String,
    val status: String,
    @SerialName("session_id") val sessionId: String? = null,
    val revision: Int? = null,
    @SerialName("character_id") val characterId: String? = null,
    @SerialName("context_epoch") val contextEpoch: Int? = null,
    val events: List<CompanionEvent> = emptyList(),
    @SerialName("expression_mode") val expressionMode: String? = null,
    @SerialName("fallback_reason") val fallbackReason: String? = null,
    @SerialName("remote_compute_cancelled") val remoteComputeCancelled: Boolean? = null,
    val error: String? = null,
)

@Serializable
data class MemoryCard(
    @SerialName("card_id") val cardId: String,
    val category: String = "",
    val title: String = "",
    val body: String = "",
    @SerialName("when_label") val whenLabel: String = "",
    @SerialName("mood_label") val moodLabel: String = "",
    val pinned: Boolean = false,
    @SerialName("source_count") val sourceCount: Int = 0,
    val actions: List<String> = emptyList(),
)

@Serializable
data class MemorySection(val category: String, val cards: List<MemoryCard> = emptyList())

@Serializable
data class PendingCandidate(
    @SerialName("pending_id") val pendingId: String,
    val title: String = "",
    val summary: String = "",
    val source: String = "",
)

@Serializable
data class MemoryAlbum(
    val title: String = "",
    val subtitle: String = "",
    @SerialName("character_id") val characterId: String,
    @SerialName("context_epoch") val contextEpoch: Int,
    val sections: List<MemorySection> = emptyList(),
    @SerialName("pending_candidates") val pendingCandidates: List<PendingCandidate> = emptyList(),
)

@Serializable
data class MemoryResponse(
    @SerialName("session_id") val sessionId: String,
    val revision: Int,
    @SerialName("character_id") val characterId: String,
    @SerialName("context_epoch") val contextEpoch: Int,
    val album: MemoryAlbum,
    val status: String? = null,
)

@Serializable
data class MemorySource(
    @SerialName("memory_id") val memoryId: String = "",
    @SerialName("chapter_id") val chapterId: String = "",
    val title: String = "",
    val summary: String = "",
    val source: String = "",
    val version: Int = 0,
    val confidence: Double = 0.0,
    @SerialName("valid_until") val validUntil: Double? = null,
    val active: Boolean = true,
    @SerialName("user_confirmed") val userConfirmed: Boolean = false,
)

@Serializable
data class SourceResponse(val source: MemorySource)

@Serializable
data class HostEvent(
    val sequence: Int,
    val type: String,
    @SerialName("character_id") val characterId: String = "",
    @SerialName("context_epoch") val contextEpoch: Int = 0,
    @SerialName("clear_cached_content") val clearCachedContent: Boolean = false,
)

@Serializable
data class EventsResponse(
    @SerialName("session_id") val sessionId: String,
    val revision: Int,
    @SerialName("character_id") val characterId: String,
    @SerialName("context_epoch") val contextEpoch: Int,
    val events: List<HostEvent> = emptyList(),
    @SerialName("resync_required") val resyncRequired: Boolean = false,
)

@Serializable
data class ErrorBody(val code: String = "", val message: String = "")

@Serializable
data class ErrorEnvelope(val error: ErrorBody)
