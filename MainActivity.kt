package com.cyberlab.twirlly

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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val Ink = Color(0xFF0A1020)
private val Panel = Color(0xFF131D31)
private val Panel2 = Color(0xFF1A2940)
private val White = Color(0xFFF4F7FC)
private val Muted = Color(0xFF9AAAC0)
private val Cyan = Color(0xFF31D6E7)
private val Orange = Color(0xFFFFA24A)
private val Purple = Color(0xFF9B7BFF)
private val Lime = Color(0xFFB9E769)
private val Coral = Color(0xFFFF7185)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { CyberLabApp() }
    }
}

private enum class Tab(val label: String, val icon: ImageVector) {
    Home("Home", Icons.Outlined.Home),
    Learn("Learn", Icons.Outlined.MenuBook),
    Labs("Labs", Icons.Outlined.Science),
    Profile("Profile", Icons.Outlined.Person)
}

@Composable
private fun CyberLabApp() {
    var selected by remember { mutableStateOf(Tab.Home) }
    var showWelcome by remember { mutableStateOf(true) }
    var selectedLesson by remember { mutableStateOf<String?>(null) }

    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Cyan,
            secondary = Orange,
            background = Ink,
            surface = Panel,
            onPrimary = Ink,
            onBackground = White,
            onSurface = White
        )
    ) {
        Surface(Modifier.fillMaxSize(), color = Ink) {
            if (showWelcome) {
                WelcomeScreen(onStart = { showWelcome = false })
            } else if (selectedLesson != null) {
                LessonScreen(
                    title = selectedLesson!!,
                    onBack = { selectedLesson = null }
                )
            } else {
                Scaffold(
                    containerColor = Ink,
                    bottomBar = {
                        NavigationBar(
                            containerColor = Color(0xFF0E1728),
                            contentColor = Muted
                        ) {
                            Tab.entries.forEach { tab ->
                                NavigationBarItem(
                                    selected = selected == tab,
                                    onClick = { selected = tab },
                                    icon = { Icon(tab.icon, contentDescription = tab.label) },
                                    label = { Text(tab.label, fontSize = 11.sp) },
                                    colors = NavigationBarItemDefaults.colors(
                                        selectedIconColor = Cyan,
                                        selectedTextColor = Cyan,
                                        indicatorColor = Color(0xFF20374B),
                                        unselectedIconColor = Muted,
                                        unselectedTextColor = Muted
                                    )
                                )
                            }
                        }
                    }
                ) { padding ->
                    Box(Modifier.fillMaxSize().padding(padding)) {
                        when (selected) {
                            Tab.Home -> HomeScreen(
                                onOpenLearn = { selected = Tab.Learn },
                                onOpenLabs = { selected = Tab.Labs },
                                onLesson = { selectedLesson = it }
                            )
                            Tab.Learn -> LearnScreen(onLesson = { selectedLesson = it })
                            Tab.Labs -> LabsScreen(onLesson = { selectedLesson = it })
                            Tab.Profile -> ProfileScreen()
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun WelcomeScreen(onStart: () -> Unit) {
    Column(
        Modifier.fillMaxSize().background(Ink).padding(horizontal = 26.dp, vertical = 30.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(46.dp).background(Cyan, RoundedCornerShape(14.dp)),
                contentAlignment = Alignment.Center
            ) { Icon(Icons.Filled.Shield, null, tint = Ink, modifier = Modifier.size(27.dp)) }
            Spacer(Modifier.width(12.dp))
            Column {
                Text("CYBERLAB", color = White, fontWeight = FontWeight.Black, fontSize = 19.sp, letterSpacing = 1.5.sp)
                Text("LEARN • PRACTICE • DEFEND", color = Muted, fontSize = 9.sp, letterSpacing = 1.2.sp)
            }
        }
        Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Box(
                Modifier.fillMaxWidth().height(220.dp)
                    .background(Panel, RoundedCornerShape(28.dp)),
                contentAlignment = Alignment.Center
            ) {
                Box(Modifier.size(142.dp).background(Color(0xFF17394A), CircleShape), contentAlignment = Alignment.Center) {
                    Box(Modifier.size(100.dp).background(Color(0xFF1B5865), CircleShape), contentAlignment = Alignment.Center) {
                        Icon(Icons.Filled.Security, null, tint = Cyan, modifier = Modifier.size(62.dp))
                    }
                }
                Text("01", Modifier.align(Alignment.TopEnd).padding(20.dp), color = Orange, fontWeight = FontWeight.Bold)
                Text("SAFE TRAINING ENVIRONMENT", Modifier.align(Alignment.BottomCenter).padding(bottom = 18.dp), color = Muted, fontSize = 10.sp, letterSpacing = 1.3.sp)
            }
            Text("Think like a defender.", color = White, fontSize = 33.sp, lineHeight = 39.sp, fontWeight = FontWeight.ExtraBold)
            Text(
                "Build real cybersecurity knowledge through guided lessons, practical simulations and challenges designed for responsible learning.",
                color = Muted, fontSize = 15.sp, lineHeight = 24.sp
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("BEGINNER FRIENDLY", Cyan)
                Pill("HANDS-ON", Orange)
                Pill("RESPONSIBLE", Lime)
            }
        }
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Button(
                onClick = onStart,
                modifier = Modifier.fillMaxWidth().height(58.dp),
                shape = RoundedCornerShape(17.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Cyan, contentColor = Ink)
            ) {
                Text("Enter CYBERLAB", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.width(10.dp))
                Icon(Icons.Filled.ArrowForward, null)
            }
            Text("A learning space for curious, responsible minds.", color = Muted, fontSize = 11.sp, modifier = Modifier.align(Alignment.CenterHorizontally))
        }
    }
}

@Composable
private fun HomeScreen(onOpenLearn: () -> Unit, onOpenLabs: () -> Unit, onLesson: (String) -> Unit) {
    LazyColumn(
        Modifier.fillMaxSize().padding(horizontal = 20.dp),
        contentPadding = PaddingValues(top = 22.dp, bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp)
    ) {
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("GOOD TO SEE YOU", color = Cyan, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.5.sp)
                    Text("Your cyber journey", color = White, fontSize = 25.sp, fontWeight = FontWeight.ExtraBold)
                }
                Box(Modifier.size(44.dp).background(Panel2, CircleShape), contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.NotificationsNone, null, tint = White)
                }
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                StatCard("LEARNING STREAK", "3 days", "Keep it going", Orange, Icons.Outlined.LocalFireDepartment, Modifier.weight(1f))
                StatCard("SKILL LEVEL", "Starter", "Level 01", Cyan, Icons.Outlined.MilitaryTech, Modifier.weight(1f))
            }
        }
        item {
            Column(Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(24.dp)).padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Pill("TODAY'S MISSION", Orange)
                    Spacer(Modifier.weight(1f))
                    Icon(Icons.Outlined.Bolt, null, tint = Orange)
                }
                Text("Become a password pro", color = White, fontSize = 21.sp, fontWeight = FontWeight.Bold)
                Text("Learn what makes a password strong and how multi-factor authentication adds another layer of protection.", color = Muted, fontSize = 13.sp, lineHeight = 20.sp)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("12 min", color = Orange, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.width(12.dp))
                    Text("•  Beginner", color = Muted, fontSize = 12.sp)
                    Spacer(Modifier.weight(1f))
                    Button(onClick = { onLesson("Become a password pro") }, shape = RoundedCornerShape(12.dp), contentPadding = PaddingValues(horizontal = 17.dp, vertical = 10.dp)) {
                        Text("Start")
                    }
                }
            }
        }
        item {
            SectionHeading("Explore CYBERLAB", "View all", onOpenLearn)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                FeatureTile("Learning paths", "Build your knowledge", Icons.Outlined.School, Purple, Modifier.weight(1f), onOpenLearn)
                FeatureTile("Practice labs", "Try safe simulations", Icons.Outlined.Science, Lime, Modifier.weight(1f), onOpenLabs)
            }
        }
        item {
            SectionHeading("Continue learning", "See lessons", onOpenLearn)
            LessonRow("01", "Cybersecurity foundations", "What are we protecting?", "8 min", Cyan) { onLesson("Cybersecurity foundations") }
            LessonRow("02", "Spot the phishing signs", "Recognise suspicious messages", "10 min", Coral) { onLesson("Spot the phishing signs") }
        }
        item {
            Row(Modifier.fillMaxWidth().background(Color(0xFF19283A), RoundedCornerShape(18.dp)).padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Lightbulb, null, tint = Orange, modifier = Modifier.size(28.dp))
                Spacer(Modifier.width(12.dp))
                Column {
                    Text("DEFENDER TIP", color = Orange, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
                    Text("Pause before you tap. Check the sender and destination of unexpected links.", color = White, fontSize = 12.sp, lineHeight = 18.sp)
                }
            }
        }
    }
}

@Composable
private fun LearnScreen(onLesson: (String) -> Unit) {
    val lessons = listOf(
        Triple("Cybersecurity foundations", "Understand threats, risk and digital safety.", Cyan),
        Triple("Password protection", "Create strong passphrases and use MFA.", Orange),
        Triple("Phishing awareness", "Identify suspicious messages and links.", Coral),
        Triple("Privacy and data", "Learn how personal information is exposed.", Purple),
        Triple("Network safety", "Understand Wi-Fi, routers and safe connections.", Lime)
    )
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 20.dp), contentPadding = PaddingValues(top = 24.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item {
            Text("LEARNING HUB", color = Cyan, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.5.sp)
            Text("Choose your next skill", color = White, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold)
            Text("Short, structured lessons that build practical defensive knowledge.", color = Muted, fontSize = 13.sp, lineHeight = 20.sp)
        }
        item { ProgressCard() }
        items(lessons) { item ->
            LessonRow("→", item.first, item.second, "8–12 min", item.third) { onLesson(item.first) }
        }
    }
}

@Composable
private fun LabsScreen(onLesson: (String) -> Unit) {
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 20.dp), contentPadding = PaddingValues(top = 24.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            Text("PRACTICE ZONE", color = Lime, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.5.sp)
            Text("Learn by doing", color = White, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold)
            Text("Interactive, offline-friendly exercises using fictional examples and safe simulations.", color = Muted, fontSize = 13.sp, lineHeight = 20.sp)
        }
        item { LabCard("01", "Phishing spotter", "Inspect a fictional message and identify warning signs.", "AWARENESS", Coral) { onLesson("Phishing spotter") } }
        item { LabCard("02", "Password strength check", "Compare sample passphrases and learn what improves them.", "ACCOUNT SAFETY", Cyan) { onLesson("Password strength check") } }
        item { LabCard("03", "Privacy detective", "Choose what information is safe to share in a sample profile.", "PRIVACY", Purple) { onLesson("Privacy detective") } }
        item { LabCard("04", "Incident response", "Practise the right steps after a fictional account alert.", "DEFENCE", Orange) { onLesson("Incident response") } }
        item {
            Text("All labs are educational simulations. They do not connect to, scan or attack real systems.", color = Muted, fontSize = 11.sp, lineHeight = 17.sp)
        }
    }
}

@Composable
private fun ProfileScreen() {
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 20.dp), contentPadding = PaddingValues(top = 26.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        item {
            Text("YOUR SPACE", color = Cyan, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.5.sp)
            Text("Learner profile", color = White, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold)
        }
        item {
            Row(Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(22.dp)).padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(58.dp).background(Color(0xFF254456), CircleShape), contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Person, null, tint = Cyan, modifier = Modifier.size(32.dp))
                }
                Spacer(Modifier.width(14.dp))
                Column {
                    Text("CYBER LEARNER", color = White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                    Text("Starter • Level 01", color = Muted, fontSize = 12.sp)
                }
            }
        }
        item { ProgressCard() }
        item { SettingRow(Icons.Outlined.EmojiEvents, "Achievements", "Your milestones and badges", Orange) }
        item { SettingRow(Icons.Outlined.BookmarkBorder, "Saved lessons", "Return to lessons you saved", Cyan) }
        item { SettingRow(Icons.Outlined.Settings, "App settings", "Personalise your learning space", Purple) }
        item { SettingRow(Icons.Outlined.Info, "About CYBERLAB", "Version 1.0 • Learn responsibly", Lime) }
    }
}

@Composable
private fun LessonScreen(title: String, onBack: () -> Unit) {
    var answer by remember(title) { mutableStateOf(-1) }
    var submitted by remember(title) { mutableStateOf(false) }
    val options = listOf("Use a unique passphrase and enable MFA", "Reuse one short password everywhere", "Share passwords with trusted friends")
    Column(Modifier.fillMaxSize().padding(22.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back", tint = White) }
            Text("LEARNING MODULE", color = Cyan, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.2.sp)
        }
        Spacer(Modifier.height(20.dp))
        Pill("GUIDED LESSON", Orange)
        Spacer(Modifier.height(14.dp))
        Text(title, color = White, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold, lineHeight = 34.sp)
        Spacer(Modifier.height(18.dp))
        Text("A good defender starts by understanding the basics. Take your time, read each example and choose the safest response.", color = Muted, fontSize = 14.sp, lineHeight = 23.sp)
        Spacer(Modifier.height(22.dp))
        Column(Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(20.dp)).padding(18.dp)) {
            Text("KEY IDEA", color = Cyan, fontWeight = FontWeight.Bold, fontSize = 10.sp, letterSpacing = 1.2.sp)
            Spacer(Modifier.height(8.dp))
            Text("Protect accounts with unique passwords, a password manager and multi-factor authentication. Never share login codes.", color = White, fontSize = 14.sp, lineHeight = 22.sp)
        }
        Spacer(Modifier.height(24.dp))
        Text("QUICK KNOWLEDGE CHECK", color = Orange, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
        Spacer(Modifier.height(10.dp))
        Text("Which choice best protects an online account?", color = White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(12.dp))
        options.forEachIndexed { index, option ->
            Row(
                Modifier.fillMaxWidth().padding(vertical = 5.dp).background(if (answer == index) Color(0xFF20394B) else Panel, RoundedCornerShape(14.dp)).clickable { answer = index; submitted = false }.padding(14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                RadioButton(selected = answer == index, onClick = { answer = index; submitted = false }, colors = RadioButtonDefaults.colors(selectedColor = Cyan, unselectedColor = Muted))
                Spacer(Modifier.width(8.dp))
                Text(option, color = White, fontSize = 13.sp, lineHeight = 18.sp)
            }
        }
        Spacer(Modifier.height(12.dp))
        Button(onClick = { submitted = true }, enabled = answer >= 0, modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(15.dp)) {
            Text("Check answer", fontWeight = FontWeight.Bold)
        }
        if (submitted) {
            Text(if (answer == 0) "Correct. Strong, unique credentials and MFA provide layered protection." else "Not quite. Choose the option that uses unique credentials and an extra sign-in factor.", color = if (answer == 0) Lime else Orange, fontSize = 13.sp, lineHeight = 19.sp, modifier = Modifier.padding(top = 14.dp))
        }
    }
}

@Composable
private fun StatCard(title: String, value: String, subtitle: String, accent: Color, icon: ImageVector, modifier: Modifier = Modifier) {
    Column(modifier.background(Panel, RoundedCornerShape(20.dp)).padding(15.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(icon, null, tint = accent, modifier = Modifier.size(22.dp))
        Text(value, color = White, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold)
        Text(title, color = Muted, fontSize = 9.sp, fontWeight = FontWeight.Bold, letterSpacing = .8.sp)
        Text(subtitle, color = accent, fontSize = 10.sp)
    }
}

@Composable
private fun FeatureTile(title: String, subtitle: String, icon: ImageVector, accent: Color, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Column(modifier.background(Panel, RoundedCornerShape(20.dp)).clickable(onClick = onClick).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(Modifier.size(40.dp).background(accent.copy(alpha = .16f), RoundedCornerShape(13.dp)), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = accent)
        }
        Text(title, color = White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
        Text(subtitle, color = Muted, fontSize = 11.sp)
    }
}

@Composable
private fun SectionHeading(title: String, action: String, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(bottom = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(title, color = White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.weight(1f))
        Text(action, color = Cyan, fontSize = 11.sp, fontWeight = FontWeight.Bold, modifier = Modifier.clickable(onClick = onClick))
    }
}

@Composable
private fun LessonRow(number: String, title: String, subtitle: String, duration: String, accent: Color, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(bottom = 9.dp).background(Panel, RoundedCornerShape(17.dp)).clickable(onClick = onClick).padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(42.dp).background(accent.copy(alpha = .15f), RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) {
            Text(number, color = accent, fontWeight = FontWeight.ExtraBold, fontSize = 14.sp)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = White, fontSize = 13.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(subtitle, color = Muted, fontSize = 11.sp, maxLines = 2)
        }
        Text(duration, color = accent, fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun LabCard(number: String, title: String, description: String, category: String, accent: Color, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(20.dp)).clickable(onClick = onClick).padding(18.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("LAB $number", color = accent, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
            Spacer(Modifier.weight(1f))
            Pill(category, accent)
        }
        Text(title, color = White, fontSize = 19.sp, fontWeight = FontWeight.Bold)
        Text(description, color = Muted, fontSize = 12.sp, lineHeight = 18.sp)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Open simulation", color = accent, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.width(6.dp))
            Icon(Icons.Filled.ArrowForward, null, tint = accent, modifier = Modifier.size(14.dp))
        }
    }
}

@Composable
private fun ProgressCard() {
    Column(Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(20.dp)).padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("YOUR PROGRESS", color = Muted, fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
            Spacer(Modifier.weight(1f))
            Text("20%", color = Cyan, fontSize = 15.sp, fontWeight = FontWeight.ExtraBold)
        }
        LinearProgressIndicator(progress = { .2f }, modifier = Modifier.fillMaxWidth().height(7.dp), color = Cyan, trackColor = Panel2)
        Text("You're building your foundation. Complete lessons to unlock more topics.", color = Muted, fontSize = 11.sp, lineHeight = 17.sp)
    }
}

@Composable
private fun SettingRow(icon: ImageVector, title: String, subtitle: String, accent: Color) {
    Row(Modifier.fillMaxWidth().background(Panel, RoundedCornerShape(16.dp)).padding(15.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = accent, modifier = Modifier.size(24.dp))
        Spacer(Modifier.width(13.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = White, fontSize = 13.sp, fontWeight = FontWeight.Bold)
            Text(subtitle, color = Muted, fontSize = 11.sp)
        }
        Icon(Icons.Outlined.ChevronRight, null, tint = Muted)
    }
}

@Composable
private fun Pill(text: String, color: Color) {
    Box(Modifier.background(color.copy(alpha = .13f), RoundedCornerShape(50)).padding(horizontal = 10.dp, vertical = 6.dp)) {
        Text(text, color = color, fontSize = 8.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = .7.sp)
    }
}
