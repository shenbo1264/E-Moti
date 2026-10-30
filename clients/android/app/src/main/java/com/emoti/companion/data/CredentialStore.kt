package com.emoti.companion.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class StoredPairing(val hostUrl: String, val deviceId: String, val token: String, val expiresAt: Double)

/**
 * Keeps the bearer credential encrypted with a non-exportable Android Keystore key.
 * Only the host URL and device id are stored in clear; backups are excluded in the manifest.
 */
class CredentialStore(context: Context) {
    private val prefs = context.getSharedPreferences("pairing", Context.MODE_PRIVATE)

    fun load(): StoredPairing? {
        val url = prefs.getString(KEY_URL, null) ?: return null
        val deviceId = prefs.getString(KEY_DEVICE, null) ?: return null
        val sealed = prefs.getString(KEY_TOKEN, null) ?: return null
        val token = runCatching { decrypt(sealed) }.getOrNull() ?: return null.also { clear() }
        return StoredPairing(url, deviceId, token, prefs.getLong(KEY_EXPIRES, 0L).toDouble())
    }

    fun save(pairing: StoredPairing) {
        prefs.edit()
            .putString(KEY_URL, pairing.hostUrl)
            .putString(KEY_DEVICE, pairing.deviceId)
            .putString(KEY_TOKEN, encrypt(pairing.token))
            .putLong(KEY_EXPIRES, pairing.expiresAt.toLong())
            .apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (store.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build()
        )
        return generator.generateKey()
    }

    private fun encrypt(plain: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
        val sealed = cipher.iv + cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(sealed, Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String): String {
        val sealed = Base64.decode(encoded, Base64.NO_WRAP)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, sealed, 0, IV_BYTES))
        return String(cipher.doFinal(sealed, IV_BYTES, sealed.size - IV_BYTES), Charsets.UTF_8)
    }

    private companion object {
        const val KEYSTORE = "AndroidKeyStore"
        const val ALIAS = "emoti_device_credential"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_BYTES = 12
        const val KEY_URL = "host_url"
        const val KEY_DEVICE = "device_id"
        const val KEY_TOKEN = "token"
        const val KEY_EXPIRES = "expires_at"
    }
}
