package com.example.smswebhook

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object LogManager {
    private const val PREF_NAME = "SmsWebhookPrefs"
    private const val KEY_LOGS = "log_json_array"

    // 로그 저장
    fun saveLog(context: Context, otp: String, isSuccess: Boolean, message: String) {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        val existingLogsStr = prefs.getString(KEY_LOGS, "[]")

        try {
            val jsonArray = JSONArray(existingLogsStr)
            val newLog = JSONObject().apply {
                put("time", SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date()))
                put("otp", otp)
                put("status", if (isSuccess) "성공" else "실패")
                put("message", message)
            }

            // 최신 로그가 위로 오게 하려면 0번 인덱스에 넣는 방법도 있지만,
            // SharedPreferences 용량을 고려해 단순 추가(put) 방식으로 구현. UI에서 역순 출력 권장.
            jsonArray.put(newLog)

            prefs.edit().putString(KEY_LOGS, jsonArray.toString()).apply()

        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    // 로그 불러오기 (UI 바인딩 용도)
    fun getLogs(context: Context): JSONArray {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        return JSONArray(prefs.getString(KEY_LOGS, "[]"))
    }

    // 로그 지우기
    fun clearLogs(context: Context) {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        prefs.edit().remove(KEY_LOGS).apply()
    }
}