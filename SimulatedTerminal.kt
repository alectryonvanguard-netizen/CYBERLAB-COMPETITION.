package com.openai.cyberlab.data

/** Training-only console. Commands inspect in-app fictional files and never run on Android. */
object SimulatedTerminal {
    fun execute(lab: Lab, command: String): String {
        val parts = command.trim().split(Regex("\\s+")).filter { it.isNotBlank() }
        if (parts.isEmpty()) return ""
        return when (parts[0].lowercase()) {
            "help" -> "Available commands:\nhelp\nls [folder]\ncat <file>\ngrep <word> <file>\nhint\nclear\nwhoami"
            "whoami" -> "trainee"
            "ls" -> {
                val prefix = parts.getOrNull(1)?.trim('/')?.takeIf { it.isNotBlank() }?.plus("/") ?: ""
                val entries = lab.files.keys.filter { it.startsWith(prefix) }
                    .map { it.removePrefix(prefix).substringBefore("/") +
                        if (it.removePrefix(prefix).contains("/")) "/" else "" }
                    .distinct().sorted()
                if (entries.isEmpty()) "No files found." else entries.joinToString("   ")
            }
            "cat" -> {
                if (parts.size < 2) "Usage: cat <file>"
                else lab.files[parts[1].trim('/')] ?: "File not found in this lab."
            }
            "grep" -> {
                if (parts.size < 3) "Usage: grep <word> <file>"
                else {
                    val content = lab.files[parts[2].trim('/')]
                    if (content == null) "File not found in this lab."
                    else content.lineSequence().filter { it.contains(parts[1], true) }
                        .joinToString("\n").ifBlank { "No matching lines." }
                }
            }
            "hint" -> "Use the hint button below the console for the next investigation clue."
            "clear" -> "Console cleared."
            else -> "Command not available in this training console. Type help."
        }
    }
}
