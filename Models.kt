package com.openai.cyberlab.data

enum class Track(val title: String, val tint: Long) {
    FOUNDATIONS("Foundations", 0xFF36D6C5),
    DEFENCE("Defence", 0xFF6C9BFF),
    ANALYSIS("Analysis", 0xFFFFB454),
    RESPONSE("Response", 0xFFCF8BFF)
}

data class Lesson(
    val id: String,
    val title: String,
    val track: Track,
    val duration: String,
    val summary: String,
    val sections: List<Pair<String, String>>,
    val question: String,
    val choices: List<String>,
    val correct: Int,
    val explanation: String
)

data class Course(
    val id: String,
    val title: String,
    val track: Track,
    val description: String,
    val lessonIds: List<String>
)

data class Lab(
    val id: String,
    val title: String,
    val difficulty: String,
    val objective: String,
    val briefing: String,
    val files: Map<String, String>,
    val hints: List<String>,
    val acceptedAnswer: String,
    val reward: Int
)

data class ToolGuide(
    val name: String,
    val category: String,
    val purpose: String,
    val safeUse: String
)
