package com.emoti.companion

import com.emoti.companion.data.HostApi
import com.emoti.companion.data.StoredPairing
import com.emoti.companion.state.CompanionSession
import com.emoti.companion.state.LineStatus
import com.emoti.companion.state.PairingStore
import com.emoti.companion.state.Phase
import com.emoti.companion.state.Role
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Replays responses recorded from a real loopback host; see recorded-host.json. */
class CompanionSessionTest {
    private val recorded: JsonObject = Json.parseToJsonElement(
        javaClass.classLoader!!.getResource("recorded-host.json")!!.readText()
    ).jsonObject
    private lateinit var server: MockWebServer
    private val routes = mutableMapOf<String, ArrayDeque<MockResponse>>()
    private val requests = mutableListOf<RecordedRequest>()
    private val store = MemoryStore()

    @Before
    fun setUp() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests += request
                val key = "${request.method} ${request.path!!.substringBefore('?')}"
                val queue = routes[key] ?: return MockResponse().setResponseCode(599)
                return if (queue.size > 1) queue.removeFirst() else queue.first()
            }
        }
        server.start(java.net.InetAddress.getByName("127.0.0.1"), 0)
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    private fun recordedBody(name: String, edit: (MutableMap<String, Any?>) -> Unit = {}): MockResponse {
        val entry = recorded[name]!!.jsonObject
        val status = (entry["status"] as JsonPrimitive).content.toInt()
        val body = entry["body"]!!.jsonObject.toMutableMap()
        val changes = mutableMapOf<String, Any?>()
        edit(changes)
        changes.forEach { (k, v) -> body[k] = if (v is Number) JsonPrimitive(v) else JsonPrimitive(v as String) }
        return MockResponse().setResponseCode(status).setBody(JsonObject(body).toString())
    }

    private fun route(key: String, vararg responses: MockResponse) {
        routes[key] = ArrayDeque(responses.toList())
    }

    private fun hostUrl() = "http://127.0.0.1:${server.port}/"

    private fun session() = CompanionSession(store, { HostApi(it) }, pollIntervalMs = 1)

    private fun pairedSession(): CompanionSession = runBlocking {
        route("POST /v1/pair", recordedBody("pair"))
        route("GET /v1/session", recordedBody("session"))
        route("GET /v1/memory", recordedBody("memory_with_pending"))
        session().also { it.pair(hostUrl(), "x".repeat(43), "test phone") }
    }

    @Test
    fun pairingStoresCredentialAndLoadsPendingMemory() {
        val s = pairedSession()
        val state = s.state.value
        assertEquals(Phase.Online, state.phase)
        assertEquals("xingxi_pixel_pet", state.characterId)
        assertEquals("recorded-token-redacted", store.saved?.token)
        assertEquals("我喜欢桂花茶", state.album!!.pendingCandidates.single().summary)
        assertEquals("Bearer recorded-token-redacted", requests.last().getHeader("Authorization"))
    }

    @Test
    fun invalidInvitationShowsErrorAndStaysUnpaired() = runBlocking {
        route("POST /v1/pair", recordedBody("pair_bad"))
        val s = session()
        s.pair(hostUrl(), "x".repeat(43), "phone")
        assertEquals(Phase.Unpaired, s.state.value.phase)
        assertTrue(s.state.value.error!!.contains("邀请码"))
        assertNull(store.saved)
    }

    @Test
    fun sendPollsUntilReplyAndEchoesVersion() = runBlocking {
        val s = pairedSession()
        route("POST /v1/messages", recordedBody("message_post"))
        server.dispatcher = withWildcardResult(server.dispatcher, recordedBody("message_result"))
        s.send("你好")
        val lines = s.state.value.messages
        assertEquals(listOf(Role.User, Role.Companion), lines.map { it.role })
        assertEquals(LineStatus.Completed, lines[0].status)
        assertEquals("唔，我听见了。你刚才说：你好", lines[1].text)
        assertNull(s.state.value.replyRequestId)
        val sent = Json.parseToJsonElement(requests.first { it.path == "/v1/messages" }.body.readUtf8()).jsonObject
        assertEquals("44709d9da8374569ae9dda7bae7b048b", (sent["session_id"] as JsonPrimitive).content)
        assertEquals("1", (sent["expected_revision"] as JsonPrimitive).content)
    }

    @Test
    fun versionChangeInEventsClearsChatAndAlbum() = runBlocking {
        val s = pairedSession()
        route("POST /v1/messages", recordedBody("message_chat_remember"))
        s.send("请记住我喜欢桂花茶")
        assertEquals(2, s.state.value.messages.size)
        route("GET /v1/events", recordedBody("events") { it["context_epoch"] = 1; it["revision"] = 2 })
        route("GET /v1/memory", recordedBody("memory") { it["context_epoch"] = 1; it["revision"] = 2 })
        s.pollEvents()
        val state = s.state.value
        assertTrue(state.messages.isEmpty())
        assertEquals(1, state.version!!.contextEpoch)
        assertTrue(state.notice!!.contains("已清除"))
        assertEquals(2, state.album!!.sections.single().cards.size)
    }

    @Test
    fun resyncRequiredRefreshesContent() = runBlocking {
        val s = pairedSession()
        route("GET /v1/events", recordedBody("events_ahead"))
        route("GET /v1/memory", recordedBody("memory"))
        s.pollEvents()
        assertEquals(2, s.state.value.album!!.sections.single().cards.size)
    }

    @Test
    fun staleWriteIsNotSilentlyResent() = runBlocking {
        val s = pairedSession()
        route("POST /v1/messages", MockResponse().setResponseCode(409)
            .setBody("""{"error":{"code":"stale_context","message":"stale"}}"""))
        s.send("你好")
        val line = s.state.value.messages.single()
        assertEquals(LineStatus.Stale, line.status)
        assertEquals(1, requests.count { it.path == "/v1/messages" })
    }

    @Test
    fun revokedCredentialReturnsToPairingAndClearsStore() = runBlocking {
        val s = pairedSession()
        route("GET /v1/events", MockResponse().setResponseCode(401)
            .setBody("""{"error":{"code":"unauthorized","message":"revoked"}}"""))
        s.pollEvents()
        assertEquals(Phase.Unauthorized, s.state.value.phase)
        assertNull(store.saved)
        assertTrue(s.state.value.messages.isEmpty())
    }

    @Test
    fun lostConnectionMarksDeliveryUnknownAndRetryKeepsRequestId() = runBlocking {
        val s = pairedSession()
        route("POST /v1/messages", MockResponse().setSocketPolicy(okhttp3.mockwebserver.SocketPolicy.DISCONNECT_AFTER_REQUEST))
        s.send("你好")
        val line = s.state.value.messages.single()
        assertEquals(LineStatus.DeliveryUnknown, line.status)
        assertEquals(Phase.Offline, s.state.value.phase)
        route("POST /v1/messages", recordedBody("message_post"))
        server.dispatcher = withWildcardResult(server.dispatcher, recordedBody("message_result"))
        s.retry(line.id)
        val ids = requests.filter { it.path == "/v1/messages" }.map {
            (Json.parseToJsonElement(it.body.readUtf8()).jsonObject["request_id"] as JsonPrimitive).content
        }
        assertEquals(2, ids.size)
        assertEquals(ids[0], ids[1])
        assertEquals(LineStatus.Completed, s.state.value.messages.first().status)
    }

    @Test
    fun cleartextIsRejectedForLanHosts() {
        assertThrows(IllegalArgumentException::class.java) { HostApi.parseBaseUrl("http://192.168.1.20:8765") }
        assertEquals("http://127.0.0.1:8765/", HostApi.parseBaseUrl("127.0.0.1:8765").toString())
        assertEquals("https://192.168.1.20:8765/", HostApi.parseBaseUrl("https://192.168.1.20:8765/").toString())
    }

    private fun withWildcardResult(inner: Dispatcher, result: MockResponse) = object : Dispatcher() {
        override fun dispatch(request: RecordedRequest): MockResponse =
            if (request.method == "GET" && request.path!!.startsWith("/v1/messages/")) {
                requests += request
                result
            } else inner.dispatch(request)
    }

    private class MemoryStore : PairingStore {
        var saved: StoredPairing? = null
        override fun load() = saved
        override fun save(pairing: StoredPairing) { saved = pairing }
        override fun clear() { saved = null }
    }
}
