package com.example.smswebhook

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class LogAdapter(private var logs: List<String>) : RecyclerView.Adapter<LogAdapter.LogViewHolder>() {

    class LogViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val tvLogItem: TextView = view.findViewById(R.id.tvLogItem)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): LogViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_log, parent, false)
        return LogViewHolder(view)
    }

    override fun onBindViewHolder(holder: LogViewHolder, position: Int) {
        holder.tvLogItem.text = logs[position]
    }

    override fun getItemCount() = logs.size

    // 데이터 갱신용 함수
    fun updateLogs(newLogs: List<String>) {
        logs = newLogs
        notifyDataSetChanged()
    }
}