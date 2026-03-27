package com.nethunterz

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.nethunterz.databinding.ItemPacketBinding
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * PacketAdapter – RecyclerView adapter for the captured NRF packet feed.
 */
class PacketAdapter : ListAdapter<PacketItem, PacketAdapter.ViewHolder>(DIFF) {

    private val timeFmt = SimpleDateFormat("HH:mm:ss.SSS", Locale.getDefault())

    inner class ViewHolder(private val binding: ItemPacketBinding) :
        RecyclerView.ViewHolder(binding.root) {

        fun bind(item: PacketItem) {
            binding.tvModuleId.text = "M${item.moduleId}"
            binding.tvChannel.text = "Ch${item.channel} (${item.freqMhz} MHz)"
            binding.tvRssi.text = "${item.rssi} dBm"
            binding.tvPayload.text = item.payload.take(32) + if (item.payload.length > 32) "…" else ""
            binding.tvTimestamp.text = timeFmt.format(Date(item.timestampMs))
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = ViewHolder(
        ItemPacketBinding.inflate(LayoutInflater.from(parent.context), parent, false)
    )

    override fun onBindViewHolder(holder: ViewHolder, position: Int) =
        holder.bind(getItem(position))

    companion object {
        val DIFF = object : DiffUtil.ItemCallback<PacketItem>() {
            override fun areItemsTheSame(a: PacketItem, b: PacketItem) = a.id == b.id
            override fun areContentsTheSame(a: PacketItem, b: PacketItem) = a == b
        }
    }
}
