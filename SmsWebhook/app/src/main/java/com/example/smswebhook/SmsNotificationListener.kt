package com.example.smswebhook

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification

class SmsNotificationListener : NotificationListenerService() {

    private var lastProcessedOtp: String? = null
    private var lastProcessedTime: Long = 0L
    private val COOLDOWN_MS = 4000L

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val extras = sbn.notification.extras

        // 텍스트 추출
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString() ?: ""

        val fullText = "$title $text $bigText"
        val textWithoutSpace = fullText.replace(" ", "")

        // CCTV 삭제 완료. 조건에 맞을 때만 깔끔하게 동작합니다.
        if (textWithoutSpace.contains("BEST시스템") && textWithoutSpace.contains("인증번호")) {

            val regex = Regex("\\d{6}")
            val matchResult = regex.find(fullText)
            val otpNumber = matchResult?.value

            if (otpNumber != null) {
                val currentTime = System.currentTimeMillis()

                // 중복 방지 쿨타임
                if (otpNumber == lastProcessedOtp && (currentTime - lastProcessedTime) < COOLDOWN_MS) {
                    return
                }

                lastProcessedOtp = otpNumber
                lastProcessedTime = currentTime

                // 통과되면 서버로 전송 (이때만 전송 성공 로그가 1줄 찍힙니다)
                NetworkManager.sendToServer(applicationContext, otpNumber)
            }
        }
    }

    companion object {
        var isServiceConnected = false
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        isServiceConnected = true
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        isServiceConnected = false
    }
}