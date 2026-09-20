package com.example.smswebhook

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationManagerCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

class MainActivity : AppCompatActivity() {

    private lateinit var tvStatus: TextView
    private lateinit var btnTest: Button
    private lateinit var btnClearLog: Button
    private lateinit var recyclerViewLogs: RecyclerView
    private lateinit var logAdapter: LogAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // UI 초기화
        tvStatus = findViewById(R.id.tvStatus)
        btnTest = findViewById(R.id.btnTest)
        btnClearLog = findViewById(R.id.btnClearLog)
        recyclerViewLogs = findViewById(R.id.recyclerViewLogs)

        // RecyclerView 설정
        logAdapter = LogAdapter(emptyList())
        recyclerViewLogs.layoutManager = LinearLayoutManager(this)
        recyclerViewLogs.adapter = logAdapter

        // 테스트 버튼 클릭 이벤트
        btnTest.setOnClickListener {
            Toast.makeText(this, "테스트 인증번호 전송 중...", Toast.LENGTH_SHORT).show()
            // 가상의 6자리 번호 전송
            NetworkManager.sendToServer(applicationContext, "123456")

            // 전송 후 로그 갱신을 위해 약간의 딜레이 후 새로고침 (실무에서는 콜백이나 LiveData를 쓰지만, 심플하게 처리)
            recyclerViewLogs.postDelayed({ loadLogs() }, 1000)
        }

        // 로그 지우기 버튼 클릭 이벤트
        btnClearLog.setOnClickListener {
            LogManager.clearLogs(this)
            loadLogs()
            Toast.makeText(this, "로그가 초기화되었습니다.", Toast.LENGTH_SHORT).show()
        }

        // 👇 여기서부터 복사해서 넣으세요! (앱 완전 종료 버튼 행동)
        val btnExit = findViewById<Button>(R.id.btnExit)
        btnExit.setOnClickListener {
            // 1. 현재 열려있는 모든 화면(Activity)을 메모리에서 해제
            finishAffinity()

            // 2. 0.2초 정도 딜레이 후 리눅스 프로세스 레벨에서 앱을 강제 사살 (Kill)
            btnExit.postDelayed({
                kotlin.system.exitProcess(0)
            }, 200)
        }
    }

    // 화면이 다시 보일 때마다 권한 상태와 로그를 갱신합니다. (매우 중요)
    override fun onResume() {
        super.onResume()
        checkPermissionsAndUpdateUI()
        loadLogs()
    }

    private fun checkPermissionsAndUpdateUI() {
        val isNotificationEnabled = isNotificationListenerEnabled()
        val isBatteryOptimizedIgnored = isIgnoringBatteryOptimizations()

        if (!isNotificationEnabled) {
            tvStatus.text = "🔴 알림 접근 권한이 필요합니다. (클릭하여 설정)"
            tvStatus.setOnClickListener {
                startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            }
        } else if (!isBatteryOptimizedIgnored) {
            tvStatus.text = "🟡 배터리 최적화 제외가 필요합니다. (클릭하여 설정)"
            tvStatus.setOnClickListener {
                val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:$packageName")
                }
                startActivity(intent)
            }
        } else {
            tvStatus.text = "🟢 서비스 정상 실행 중"
            tvStatus.setOnClickListener(null) // 클릭 이벤트 제거
        }
    }

    // 1. 알림 접근 허용 여부 체크
    private fun isNotificationListenerEnabled(): Boolean {
        val enabledListeners = NotificationManagerCompat.getEnabledListenerPackages(this)
        return enabledListeners.contains(packageName)
    }

    // 2. 배터리 최적화 예외 여부 체크
    private fun isIgnoringBatteryOptimizations(): Boolean {
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        return powerManager.isIgnoringBatteryOptimizations(packageName)
    }

    // SharedPreferences에서 로그를 읽어와 RecyclerView에 뿌려주는 함수
    private fun loadLogs() {
        val jsonArray = LogManager.getLogs(this)
        val logList = mutableListOf<String>()

        // 최신 로그가 위에 보이도록 역순으로 List에 담습니다.
        for (i in jsonArray.length() - 1 downTo 0) {
            val logObj = jsonArray.getJSONObject(i)
            val time = logObj.getString("time")
            val status = logObj.getString("status")
            val otp = logObj.getString("otp")
            val message = logObj.optString("message", "")

            // 예시: [2026-03-17 12:45] 전송 성공 - 502320
            val logString = "[$time] 전송 $status - $otp" + if (status == "실패") " ($message)" else ""
            logList.add(logString)
        }

        logAdapter.updateLogs(logList)
    }
}