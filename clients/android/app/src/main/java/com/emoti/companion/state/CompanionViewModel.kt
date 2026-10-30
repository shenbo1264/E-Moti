package com.emoti.companion.state

import android.app.Application
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.emoti.companion.data.CredentialStore
import com.emoti.companion.data.MemorySource
import com.emoti.companion.data.StoredPairing
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class CompanionViewModel(application: Application) : AndroidViewModel(application) {
    private val credentials = CredentialStore(application)
    val session = CompanionSession(object : PairingStore {
        override fun load() = credentials.load()
        override fun save(pairing: StoredPairing) = credentials.save(pairing)
        override fun clear() = credentials.clear()
    })
    val state = session.state
    val defaultDeviceName: String = "${Build.MANUFACTURER} ${Build.MODEL}".trim().take(80)

    init {
        session.restore()
    }

    /** Foreground-only sync: refresh once, then poll invalidation events. No background service. */
    suspend fun foregroundSync() {
        if (state.value.phase in setOf(Phase.Unpaired, Phase.Pairing, Phase.Unauthorized)) return
        session.refresh()
        while (true) {
            delay(EVENT_POLL_MS)
            session.pollEvents()
        }
    }

    fun pair(hostUrl: String, invitation: String, deviceName: String) =
        viewModelScope.launch { session.pair(hostUrl, invitation, deviceName) }

    fun unpair() = session.unpair()
    fun send(text: String) = viewModelScope.launch { session.send(text) }
    fun retry(lineId: String) = viewModelScope.launch { session.retry(lineId) }
    fun cancelReply() = viewModelScope.launch { session.cancelReply() }
    fun refresh() = viewModelScope.launch { session.refresh() }
    fun remember(text: String) = viewModelScope.launch { session.remember(text) }
    fun confirm(pendingId: String) = viewModelScope.launch { session.confirm(pendingId) }
    fun correct(memoryId: String, title: String, text: String) =
        viewModelScope.launch { session.correct(memoryId, title, text) }
    fun forget(memoryId: String) = viewModelScope.launch { session.forget(memoryId) }
    fun loadSource(memoryId: String, onLoaded: (MemorySource?) -> Unit) =
        viewModelScope.launch { onLoaded(session.source(memoryId)) }
    fun dismissNotice() = session.dismissNotice()

    private companion object {
        const val EVENT_POLL_MS = 3000L
    }
}
