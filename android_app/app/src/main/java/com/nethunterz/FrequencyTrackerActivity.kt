package com.nethunterz

import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.nethunterz.databinding.ActivityFrequencyTrackerBinding

/**
 * FrequencyTrackerActivity – Visualises live frequency channel usage
 * and upgrade history using a line chart.
 */
class FrequencyTrackerActivity : AppCompatActivity() {

    private lateinit var binding: ActivityFrequencyTrackerBinding

    companion object {
        fun start(context: Context) =
            context.startActivity(Intent(context, FrequencyTrackerActivity::class.java))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityFrequencyTrackerBinding.inflate(layoutInflater)
        setContentView(binding.root)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        title = getString(R.string.title_freq_tracker)

        setupChart()
    }

    private fun setupChart() {
        // Placeholder dataset – in production fed by ViewModel LiveData
        val entries = listOf(
            Entry(0f, 76f),
            Entry(1f, 76f),
            Entry(2f, 100f),
            Entry(3f, 100f),
            Entry(4f, 110f),
        )
        val dataset = LineDataSet(entries, "Module 0 Channel").apply {
            color = getColor(R.color.colorPrimary)
            lineWidth = 2f
            setDrawCircles(true)
            setDrawValues(true)
        }
        binding.lineChart.apply {
            data = LineData(dataset)
            description.text = "Frequency Channel History"
            animateX(500)
            invalidate()
        }
    }

    override fun onSupportNavigateUp(): Boolean {
        onBackPressedDispatcher.onBackPressed()
        return true
    }
}
