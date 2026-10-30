package com.emoti.companion.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

/** A structured host refusal. [code] is the contract error code, e.g. stale_context. */
class HostException(val status: Int, val code: String, message: String) : Exception(message)

/** The host could not be reached or the response was lost; delivery of a write is unknown. */
class HostUnreachableException(cause: IOException) : Exception(cause.message, cause)

class HostApi(
    baseUrl: String,
    private val token: String? = null,
    private val client: OkHttpClient = defaultClient(),
) {
    val base: HttpUrl = parseBaseUrl(baseUrl)

    fun withToken(token: String) = HostApi(base.toString(), token, client)

    suspend fun pair(invitation: String, deviceName: String): PairResponse =
        post("v1/pair", PairRequest(invitation.trim(), deviceName), PairRequest.serializer(), PairResponse.serializer())

    suspend fun session(): SessionInfo = get("v1/session", SessionInfo.serializer())

    suspend fun events(after: Int): EventsResponse =
        get("v1/events?after=$after", EventsResponse.serializer())

    suspend fun sendMessage(body: MessageRequest): MessageResult =
        post("v1/messages", body, MessageRequest.serializer(), MessageResult.serializer())

    suspend fun messageResult(requestId: String): MessageResult =
        get("v1/messages/$requestId", MessageResult.serializer())

    suspend fun cancel(body: CancelRequest): MessageResult =
        post("v1/cancel", body, CancelRequest.serializer(), MessageResult.serializer())

    suspend fun memory(): MemoryResponse = get("v1/memory", MemoryResponse.serializer())

    suspend fun source(memoryId: String): SourceResponse =
        get("v1/memory/$memoryId/source", SourceResponse.serializer())

    suspend fun editMemory(body: MemoryRequest): MemoryResponse =
        post("v1/memory", body, MemoryRequest.serializer(), MemoryResponse.serializer())

    private suspend fun <T> get(path: String, out: KSerializer<T>): T =
        execute(request(path).get().build(), out)

    private suspend fun <B, T> post(path: String, body: B, inSer: KSerializer<B>, out: KSerializer<T>): T {
        val payload = json.encodeToString(inSer, body).toRequestBody(JSON_MEDIA)
        return execute(request(path).post(payload).build(), out)
    }

    private fun request(path: String): Request.Builder {
        val url = base.resolve(path) ?: throw IllegalArgumentException("invalid path $path")
        return Request.Builder().url(url).apply {
            if (token != null) header("Authorization", "Bearer $token")
        }
    }

    private suspend fun <T> execute(request: Request, out: KSerializer<T>): T = withContext(Dispatchers.IO) {
        try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    val error = runCatching { json.decodeFromString(ErrorEnvelope.serializer(), text).error }
                        .getOrDefault(ErrorBody())
                    throw HostException(response.code, error.code.ifEmpty { "http_${response.code}" }, error.message)
                }
                json.decodeFromString(out, text)
            }
        } catch (exc: IOException) {
            throw HostUnreachableException(exc)
        }
    }

    companion object {
        private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
        val json = Json { ignoreUnknownKeys = true; explicitNulls = false; encodeDefaults = true }

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .retryOnConnectionFailure(false)
            .build()

        /** Accepts "127.0.0.1:8765" or a full URL; plain http is only allowed for loopback/emulator hosts. */
        fun parseBaseUrl(raw: String): HttpUrl {
            val trimmed = raw.trim().trimEnd('/')
            val withScheme = if ("://" in trimmed) trimmed else "http://$trimmed"
            val url = "$withScheme/".toHttpUrlOrNull() ?: throw IllegalArgumentException("电脑地址格式不正确")
            if (url.scheme == "http" && url.host !in CLEARTEXT_HOSTS) {
                throw IllegalArgumentException("局域网地址需要 https；USB 调试请用 127.0.0.1，模拟器用 10.0.2.2")
            }
            return url
        }

        val CLEARTEXT_HOSTS = setOf("127.0.0.1", "localhost", "10.0.2.2")
    }
}
