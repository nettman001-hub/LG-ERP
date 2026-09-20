package com.example.smswebhook

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.FormBody
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

object NetworkManager {
    // 타임아웃 10초 설정 (네트워크 일시적 끊김 대응)
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    // 설계서 반영: HTTP 엔드포인트
    private const val URL = "http://unione24.co.kr/otp/sms_receiver.php"

    fun sendToServer(context: Context, otp: String) {
        // 백그라운드 스레드에서 실행
        CoroutineScope(Dispatchers.IO).launch {
            try {
                // Form-urlencoded 포맷 세팅 (otp=502320)
                val formBody = FormBody.Builder()
                    .add("otp", otp)
                    .build()

                val request = Request.Builder()
                    .url(URL)
                    .post(formBody)
                    .build()

                val response = client.newCall(request).execute()

                if (response.isSuccessful) {
                    LogManager.saveLog(context, otp, true, "전송 성공")
                } else {
                    // 실패 시 재시도 없이 로그만 기록 (설계서 5번 반영)
                    LogManager.saveLog(context, otp, false, "서버 에러(${response.code})")
                }
                response.close() // 메모리 누수 방지

            } catch (e: Exception) {
                // Timeout, 와이파이 전환 등 Exception 발생 시 로그 기록
                LogManager.saveLog(context, otp, false, "예외 발생: ${e.localizedMessage}")
            }
        }
    }
}