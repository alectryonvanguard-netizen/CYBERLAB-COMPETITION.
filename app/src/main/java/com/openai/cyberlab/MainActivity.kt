package com.openai.cyberlab

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.openai.cyberlab.data.*

private val Ink = Color(0xFF080B14)
private val Panel = Color(0xFF111827)
private val Panel2 = Color(0xFF182235)
private val White = Color(0xFFF4F7FC)
private val Muted = Color(0xFF9AA8BC)
private val Cyan = Color(0xFF36D6C5)
private val Blue = Color(0xFF6C9BFF)
private val Orange = Color(0xFFFFB454)
private val Purple = Color(0xFFCF8BFF)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val store = ProgressStore(applicationContext)
        setContent { CyberLabApp(store) }
    }
}

private enum class Page(val label: String) {
    HOME("Home"), LEARN("Learn"), LABS("Labs"), TOOLS("Tools"), PROFILE("Profile")
}

@Composable
private fun CyberLabApp(store: ProgressStore) {
    var page by remember { mutableStateOf(Page.HOME) }
    var selectedLesson by remember { mutableStateOf<String?>(null) }
    var selectedLab by remember { mutableStateOf<String?>(null) }

    MaterialTheme(
        colorScheme = darkColorScheme(
            background = Ink, surface = Panel, primary = Cyan,
            onBackground = White, onSurface = White
        )
    ) {
        Surface(Modifier.fillMaxSize(), color = Ink) {
            Column {
                if (selectedLesson != null) {
                    LessonScreen(store, selectedLesson!!, onBack = { selectedLesson = null })
                } else if (selectedLab != null) {
                    LabScreen(store, selectedLab!!, onBack = { selectedLab = null })
                } else {
                    when (page) {
                        Page.HOME -> HomeScreen(store, onPage = { page = it }, onLesson = { selectedLesson = it }, onLab = { selectedLab = it })
                        Page.LEARN -> LearnScreen(store, onLesson = { selectedLesson = it })
                        Page.LABS -> LabsScreen(store, onLab = { selectedLab = it })
                        Page.TOOLS -> ToolsScreen()
                        Page.PROFILE -> ProfileScreen(store)
                    }
                    NavigationBar(containerColor = Panel, contentColor = Muted) {
                        Page.values().forEach { item ->
                            NavigationBarItem(
                                selected = page == item,
                                onClick = { page = item },
                                icon = {
                                    Icon(
                                        when (item) {
                                            Page.HOME -> Icons.Outlined.Home
                                            Page.LEARN -> Icons.Outlined.MenuBook
                                            Page.LABS -> Icons.Outlined.Terminal
                                            Page.TOOLS -> Icons.Outlined.Build
                                            Page.PROFILE -> Icons.Outlined.Person
                                        }, contentDescription = item.label
                                    )
                                },
                                label = { Text(item.label, fontSize = 10.sp) },
                                colors = NavigationBarItemDefaults.colors(
                                    selectedIconColor = Cyan, selectedTextColor = Cyan,
                                    indicatorColor = Panel2, unselectedIconColor = Muted,
                                    unselectedTextColor = Muted
                                )
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ScreenHeader(title: String, subtitle: String? = null, back: (() -> Unit)? = null) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (back != null) {
            IconButton(onClick = back) {
                Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back", tint = White)
            }
        }
        Column(Modifier.weight(1f)) {
            Text(title, fontSize = 24.sp, fontWeight = FontWeight.Bold, color = White)
            if (subtitle != null) Text(subtitle, color = Muted, fontSize = 12.sp)
        }
        Text("CL", color = Cyan, fontWeight = FontWeight.Black, fontSize = 18.sp,
            modifier = Modifier.background(Panel2, RoundedCornerShape(12.dp)).padding(10.dp))
    }
}

@Composable
private fun HomeScreen(
    store: ProgressStore, onPage: (Page) -> Unit,
    onLesson: (String) -> Unit, onLab: (String) -> Unit
) {
    LazyColumn(contentPadding = PaddingValues(bottom = 18.dp)) {
        item {
            ScreenHeader("CYBERLAB", "Learn carefully. Investigate responsibly.")
            Column(Modifier.padding(horizontal = 18.dp)) {
                Box(Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(22.dp)).padding(18.dp)) {
                    Column {
                        Text("YOUR TRAINING SPACE", color = Cyan, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.5.sp)
                        Spacer(Modifier.height(8.dp))
                        Text(if (store.learner.isBlank()) "Welcome, analyst." else "Welcome back, ${store.learner}.",
                            color = White, fontSize = 23.sp, fontWeight = FontWeight.Bold)
                        Text("Build practical security judgement one activity at a time.", color = Muted, fontSize = 13.sp)
                        Spacer(Modifier.height(18.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Stat("LEVEL ${store.level}", "Learner rank", Cyan, Modifier.weight(1f))
                            Spacer(Modifier.width(10.dp))
                            Stat("${store.xp} XP", "Experience", Orange, Modifier.weight(1f))
                            Spacer(Modifier.width(10.dp))
                            Stat("${store.completedLessons.size}", "Lessons", Purple, Modifier.weight(1f))
                        }
                        Spacer(Modifier.height(14.dp))
                        LinearProgressIndicator(
                            progress = { store.levelProgress },
                            modifier = Modifier.fillMaxWidth().height(7.dp),
                            color = Cyan, trackColor = Panel2
                        )
                        Text("${store.xp % 250} / 250 XP to next level", color = Muted, fontSize = 10.sp)
                    }
                }
                Spacer(Modifier.height(18.dp))
                Text("PICK UP WHERE YOU LEFT OFF", color = Muted, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(9.dp))
                ActionCard("Continue learning", "Short lessons and knowledge checks", Cyan, Icons.Outlined.MenuBook) { onPage(Page.LEARN) }
                ActionCard("Enter a practice lab", "Investigate fictional evidence offline", Orange, Icons.Outlined.Terminal) { onPage(Page.LABS) }
                Spacer(Modifier.height(18.dp))
                Text("FEATURED LESSON", color = Muted, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                val featured = Content.lessons.first()
                ContentCard(featured.title, featured.summary, "LESSON · ${featured.duration}", Cyan) { onLesson(featured.id) }
                Spacer(Modifier.height(18.dp))
                Text("FEATURED PRACTICE", color = Muted, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                val lab = Content.labs.first()
                ContentCard(lab.title, lab.objective, "SIMULATED LAB · ${lab.difficulty}", Orange) { onLab(lab.id) }
            }
        }
    }
}

@Composable
private fun Stat(
    value: String,
    label: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Column(
        modifier
            .background(Panel2, RoundedCornerShape(12.dp))
            .padding(10.dp)
    ) {
        Text(value, color = color, fontWeight = FontWeight.Bold, fontSize = 15.sp)
        Text(label, color = Muted, fontSize = 9.sp)
    }
}

@Composable
private fun ActionCard(title: String, body: String, tint: Color, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(top = 8.dp).background(Panel, RoundedCornerShape(16.dp))
            .clickable { onClick() }.padding(15.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, null, tint = tint, modifier = Modifier.size(27.dp))
        Column(Modifier.weight(1f).padding(start = 12.dp)) {
            Text(title, color = White, fontWeight = FontWeight.SemiBold)
            Text(body, color = Muted, fontSize = 11.sp)
        }
        Icon(Icons.Outlined.ChevronRight, null, tint = Muted)
    }
}

@Composable
private fun ContentCard(title: String, body: String, tag: String, tint: Color, onClick: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(bottom = 9.dp).background(Panel, RoundedCornerShape(16.dp))
            .clickable { onClick() }.padding(15.dp)
    ) {
        Text(tag, color = tint, fontSize = 9.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
        Spacer(Modifier.height(5.dp))
        Text(title, color = White, fontWeight = FontWeight.Bold, fontSize = 17.sp)
        Text(body, color = Muted, fontSize = 12.sp)
    }
}

@Composable
private fun LearnScreen(store: ProgressStore, onLesson: (String) -> Unit) {
    LazyColumn(contentPadding = PaddingValues(bottom = 18.dp)) {
        item { ScreenHeader("Learning paths", "Offline lessons with short knowledge checks") }
        items(Content.courses) { course ->
            Column(Modifier.padding(horizontal = 18.dp, vertical = 6.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(9.dp).background(Color(course.track.tint), CircleShape))
                    Text(course.title, color = White, fontWeight = FontWeight.Bold, fontSize = 17.sp,
                        modifier = Modifier.padding(start = 9.dp).weight(1f))
                    Text("${course.lessonIds.count { id -> id in store.completedLessons }}/${course.lessonIds.size}",
                        color = Muted, fontSize = 11.sp)
                }
                Text(course.description, color = Muted, fontSize = 11.sp, modifier = Modifier.padding(start = 18.dp, top = 3.dp))
                course.lessonIds.forEach { id ->
                    val lesson = Content.lesson(id) ?: return@forEach
                    Row(
                        Modifier.fillMaxWidth().padding(top = 8.dp).background(Panel, RoundedCornerShape(13.dp))
                            .clickable { onLesson(id) }.padding(13.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(if (id in store.completedLessons) Icons.Outlined.CheckCircle else Icons.Outlined.MenuBook,
                            null, tint = Color(course.track.tint))
                        Column(Modifier.weight(1f).padding(start = 10.dp)) {
                            Text(lesson.title, color = White, fontWeight = FontWeight.Medium)
                            Text("${lesson.duration}  ·  +50 XP", color = Muted, fontSize = 10.sp)
                        }
                        Icon(Icons.Outlined.ChevronRight, null, tint = Muted)
                    }
                }
            }
        }
    }
}

@Composable
private fun LessonScreen(store: ProgressStore, id: String, onBack: () -> Unit) {
    val lesson = Content.lesson(id) ?: run { onBack(); return }
    var answer by remember(id) { mutableIntStateOf(-1) }
    var submitted by remember(id) { mutableStateOf(false) }
    LazyColumn(contentPadding = PaddingValues(bottom = 28.dp)) {
        item { ScreenHeader(lesson.title, lesson.duration, onBack) }
        item {
            Column(Modifier.padding(horizontal = 18.dp)) {
                Text(lesson.summary, color = Muted, fontSize = 14.sp)
                lesson.sections.forEachIndexed { index, section ->
                    Spacer(Modifier.height(14.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("0${index + 1}", color = Cyan, fontWeight = FontWeight.Bold)
                        Text(section.first, color = White, fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(start = 9.dp))
                    }
                    Text(section.second, color = Muted, fontSize = 13.sp, modifier = Modifier.padding(top = 5.dp))
                }
                Spacer(Modifier.height(22.dp))
                Text("KNOWLEDGE CHECK", color = Cyan, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Text(lesson.question, color = White, fontWeight = FontWeight.SemiBold, fontSize = 17.sp,
                    modifier = Modifier.padding(top = 8.dp, bottom = 10.dp))
                lesson.choices.forEachIndexed { index, choice ->
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 4.dp)
                            .background(if (answer == index) Panel2 else Panel, RoundedCornerShape(12.dp))
                            .clickable(enabled = !submitted) { answer = index }.padding(13.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(selected = answer == index, onClick = { if (!submitted) answer = index },
                            enabled = !submitted, colors = RadioButtonDefaults.colors(selectedColor = Cyan))
                        Text(choice, color = White, fontSize = 13.sp)
                    }
                }
                if (!submitted) {
                    Button(
                        onClick = { submitted = true; if (answer == lesson.correct) store.completeLesson(id, 50) },
                        enabled = answer >= 0, modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Cyan, contentColor = Ink)
                    ) { Text("Check answer", fontWeight = FontWeight.Bold) }
                } else {
                    val correct = answer == lesson.correct
                    Text(if (correct) "Correct — 50 XP awarded if this is your first completion." else "Not quite. Review the explanation and try another lesson.",
                        color = if (correct) Cyan else Orange, fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(top = 14.dp))
                    Text(lesson.explanation, color = Muted, fontSize = 13.sp, modifier = Modifier.padding(top = 5.dp))
                }
                if (id in store.completedLessons) Text("Previously completed", color = Cyan, fontSize = 12.sp,
                    modifier = Modifier.padding(top = 10.dp))
            }
        }
    }
}

@Composable
private fun LabsScreen(store: ProgressStore, onLab: (String) -> Unit) {
    LazyColumn(contentPadding = PaddingValues(bottom = 20.dp)) {
        item { ScreenHeader("Practice labs", "Fictional datasets · simulated console · offline") }
        item {
            Text("These exercises use only files bundled inside CYBERLAB. Commands do not run on your phone or contact external systems.",
                color = Muted, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 18.dp, vertical = 5.dp))
        }
        items(Content.labs) { lab ->
            ContentCard(
                lab.title + if (lab.id in store.completedLabs) "  ✓" else "",
                lab.objective, "${lab.difficulty.uppercase()} · +${lab.reward} XP",
                if (lab.difficulty == "Beginner") Cyan else Orange
            ) { onLab(lab.id) }
        }
    }
}

@Composable
private fun LabScreen(store: ProgressStore, id: String, onBack: () -> Unit) {
    val lab = Content.labs.firstOrNull { it.id == id } ?: run { onBack(); return }
    var command by remember(id) { mutableStateOf("") }
    var output by remember(id) { mutableStateOf("CYBERLAB TRAINING CONSOLE v1.0\nType help to see available commands.\n") }
    var hintIndex by remember(id) { mutableIntStateOf(0) }
    var submission by remember(id) { mutableStateOf("") }
    var result by remember(id) { mutableStateOf<String?>(null) }

    Column(Modifier.fillMaxSize()) {
        ScreenHeader(lab.title, "SIMULATED LAB · ${lab.difficulty}", onBack)
        LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(horizontal = 18.dp, vertical = 6.dp)) {
            item {
                Text("MISSION BRIEF", color = Orange, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                Text(lab.briefing, color = Muted, fontSize = 13.sp, modifier = Modifier.padding(top = 5.dp, bottom = 12.dp))
                Text("CONSOLE", color = Cyan, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                Text(output, color = Color(0xFFB8F5D5), fontSize = 12.sp,
                    modifier = Modifier.fillMaxWidth().background(Color(0xFF050A0A), RoundedCornerShape(14.dp)).padding(13.dp))
                Row(Modifier.padding(top = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                    BasicTextField(
                        value = command, onValueChange = { command = it },
                        modifier = Modifier.weight(1f).background(Panel, RoundedCornerShape(10.dp)).padding(12.dp),
                        textStyle = androidx.compose.ui.text.TextStyle(color = White, fontSize = 13.sp),
                        singleLine = true, decorationBox = { inner ->
                            if (command.isEmpty()) Text("Enter a training command…", color = Muted, fontSize = 12.sp)
                            inner()
                        }
                    )
                    Spacer(Modifier.width(7.dp))
                    Button(onClick = {
                        val cmd = command.trim()
                        if (cmd.equals("clear", true)) output = ""
                        else output += "\n> $cmd\n${SimulatedTerminal.execute(lab, cmd)}\n"
                        command = ""
                    }, colors = ButtonDefaults.buttonColors(containerColor = Cyan, contentColor = Ink)) {
                        Text("Run")
                    }
                }
                OutlinedButton(onClick = {
                    val hint = lab.hints.getOrNull(hintIndex)
                    if (hint != null) { output += "\n[HINT] $hint\n"; hintIndex++ }
                    else output += "\n[HINT] No more hints. Review the evidence carefully.\n"
                }, modifier = Modifier.padding(top = 6.dp)) { Text("Show hint (${minOf(hintIndex + 1, lab.hints.size)}/${lab.hints.size})") }
                Spacer(Modifier.height(18.dp))
                Text("SUBMIT FINDING", color = Orange, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                OutlinedTextField(
                    value = submission, onValueChange = { submission = it },
                    modifier = Modifier.fillMaxWidth().padding(top = 7.dp),
                    label = { Text("Your finding") }, singleLine = true
                )
                Button(
                    onClick = {
                        val correct = submission.trim().equals(lab.acceptedAnswer, ignoreCase = true)
                        result = if (correct) {
                            val first = store.completeLab(id, lab.reward)
                            if (first) "Correct! +${lab.reward} XP." else "Correct! This lab was already completed."
                        } else "Not quite. Revisit the evidence and try again."
                    },
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Orange, contentColor = Ink)
                ) { Text("Submit finding", fontWeight = FontWeight.Bold) }
                result?.let { Text(it, color = if (it.startsWith("Correct")) Cyan else Orange,
                    modifier = Modifier.padding(top = 10.dp), fontWeight = FontWeight.Bold) }
                if (id in store.completedLabs) Text("Lab completed", color = Cyan, modifier = Modifier.padding(top = 8.dp))
            }
        }
    }
}

@Composable
private fun ToolsScreen() {
    LazyColumn(contentPadding = PaddingValues(bottom = 18.dp)) {
        item { ScreenHeader("Tool reference", "Understand what common tools are for") }
        items(Content.tools) { tool ->
            Column(Modifier.padding(horizontal = 18.dp, vertical = 6.dp)
                .background(Panel, RoundedCornerShape(15.dp)).padding(15.dp)) {
                Text(tool.category.uppercase(), color = Purple, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                Text(tool.name, color = White, fontSize = 17.sp, fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 3.dp))
                Text(tool.purpose, color = Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 5.dp))
                Text("RESPONSIBLE USE", color = Cyan, fontSize = 9.sp, fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(top = 10.dp))
                Text(tool.safeUse, color = Muted, fontSize = 11.sp, modifier = Modifier.padding(top = 3.dp))
            }
        }
    }
}

@Composable
private fun ProfileScreen(store: ProgressStore) {
    var name by remember { mutableStateOf(store.learner) }
    LazyColumn(contentPadding = PaddingValues(bottom = 20.dp)) {
        item {
            ScreenHeader("Your progress", "Saved locally on this device")
            Column(Modifier.padding(horizontal = 18.dp)) {
                Text("LEARNER NAME", color = Muted, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                OutlinedTextField(name, { name = it }, modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
                    singleLine = true, label = { Text("Name or nickname") })
                Button(onClick = { store.setLearner(name) }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Cyan, contentColor = Ink)) {
                    Text("Save profile")
                }
                Spacer(Modifier.height(20.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Security checklist", color = White, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    Text("${store.checklistDone.size}/${Content.checklist.size}", color = Cyan)
                }
                Text("A personal reminder list. These checks are stored offline.", color = Muted, fontSize = 11.sp)
                Content.checklist.forEachIndexed { index, item ->
                    val id = "check-$index"
                    Row(
                        Modifier.fillMaxWidth().padding(top = 8.dp).background(Panel, RoundedCornerShape(12.dp))
                            .clickable { store.toggleChecklist(id) }.padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Checkbox(store.checklistDone.contains(id), { store.toggleChecklist(id) },
                            colors = CheckboxDefaults.colors(checkedColor = Cyan))
                        Text(item, color = White, fontSize = 12.sp)
                    }
                }
                Spacer(Modifier.height(20.dp))
                Text("ABOUT OFFLINE MODE", color = Orange, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                Text("Lessons, practice labs, tool notes and progress are available offline. Cloud backup and optional AI services are planned for a later online extension; this build does not require an account or internet connection.",
                    color = Muted, fontSize = 12.sp, modifier = Modifier.padding(top = 5.dp))
            }
        }
    }
}
