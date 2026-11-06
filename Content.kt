package com.openai.cyberlab.data

object Content {
    val lessons = listOf(
        Lesson(
            "trust-boundaries", "Trust boundaries", Track.FOUNDATIONS, "7 min",
            "Understand where responsibility and permission begin and end.",
            listOf(
                "Permission first" to "Security work begins with clear, written permission. A system being reachable does not mean it is available for testing.",
                "Scope matters" to "A scope defines the approved systems, dates, methods, data handling rules and reporting route.",
                "Protect evidence" to "Collect only what is necessary. Keep notes factual, protect sensitive information and stop when activity leaves the approved scope."
            ),
            "Which statement best describes authorised testing?",
            listOf("Anything reachable can be tested", "Testing follows documented permission and scope", "Testing is allowed if no damage is intended"),
            1, "Permission, scope and agreed rules define responsible testing."
        ),
        Lesson(
            "network-map", "Reading a network map", Track.FOUNDATIONS, "9 min",
            "Learn what common network diagrams communicate.",
            listOf(
                "Endpoints" to "Endpoints include laptops, phones, servers and other devices that communicate over a network.",
                "Segments" to "Routers, switches, firewalls and VLANs help organise traffic and separate trust zones.",
                "Defensive value" to "A current network map helps defenders understand exposure, dependencies and where monitoring is needed."
            ),
            "What does a network segment help an organisation do?",
            listOf("Separate groups of systems and traffic", "Guarantee every device is secure", "Replace identity controls"),
            0, "Segmentation helps limit unnecessary communication between groups of systems."
        ),
        Lesson(
            "identity-basics", "Identity and access basics", Track.DEFENCE, "8 min",
            "Explore authentication, authorisation and least privilege.",
            listOf(
                "Authentication" to "Authentication checks who or what is requesting access.",
                "Authorisation" to "Authorisation determines which actions an authenticated identity may perform.",
                "Least privilege" to "Give accounts only the access needed for their role, review it regularly and remove access when it is no longer needed."
            ),
            "What is the principle of least privilege?",
            listOf("Give everyone administrator access", "Give only the access needed for a task", "Never review permissions"),
            1, "Least privilege reduces the impact of mistakes and compromised accounts."
        ),
        Lesson(
            "secure-logs", "Making sense of security logs", Track.ANALYSIS, "10 min",
            "Use timestamps, event types and context to understand a fictional incident.",
            listOf(
                "Time matters" to "Check time zones, clock drift and event ordering before drawing conclusions.",
                "Context matters" to "One failed sign-in may be ordinary. A pattern across accounts, devices and locations may deserve investigation.",
                "Be precise" to "Separate observed facts from hypotheses and record the evidence behind each conclusion."
            ),
            "What should an analyst do before comparing timestamps from two systems?",
            listOf("Assume both clocks match", "Check their time zones and clock settings", "Delete older events"),
            1, "Reliable timelines require consistent time references."
        ),
        Lesson(
            "incident-triage", "Incident triage", Track.RESPONSE, "8 min",
            "Learn a calm, evidence-led approach to an alert.",
            listOf(
                "Validate" to "Confirm what triggered the alert and whether the evidence is reliable.",
                "Prioritise" to "Consider affected assets, business importance, confidence and potential impact.",
                "Escalate" to "Follow the organisation's incident plan. Preserve evidence and contact the responsible team."
            ),
            "What is a good first step when an alert arrives?",
            listOf("Immediately wipe the affected device", "Validate the alert and gather context", "Post the alert publicly"),
            1, "Triage starts by validating the signal and understanding the context."
        ),
        Lesson(
            "backup-resilience", "Backup and recovery", Track.DEFENCE, "6 min",
            "Understand why backups must be protected and tested.",
            listOf(
                "Multiple copies" to "Keep important data in more than one protected location.",
                "Separate access" to "Backups should not be equally exposed to the same accounts and systems as production data.",
                "Test recovery" to "A backup is useful only if the organisation can restore it within its recovery goals."
            ),
            "Why should recovery be tested?",
            listOf("To confirm data can actually be restored", "To make backups publicly accessible", "To avoid documenting procedures"),
            0, "Restore tests prove that backups are usable when needed."
        )
    )

    val courses = listOf(
        Course("start", "Security thinking", Track.FOUNDATIONS, "Build the habits behind responsible security work.", listOf("trust-boundaries", "network-map")),
        Course("protect", "Protecting systems", Track.DEFENCE, "Understand identity controls and resilient systems.", listOf("identity-basics", "backup-resilience")),
        Course("observe", "Security observation", Track.ANALYSIS, "Read events carefully and build evidence-led conclusions.", listOf("secure-logs")),
        Course("respond", "Incident response", Track.RESPONSE, "Practise structured, calm incident handling.", listOf("incident-triage"))
    )

    val labs = listOf(
        Lab(
            "signin-review", "The unusual sign-in", "Beginner",
            "Identify the account with repeated failed sign-ins in a fictional audit export.",
            "A training organisation has supplied a small, fictional sign-in report. Review the file and identify the account that needs a closer review. All names and addresses are invented.",
            mapOf("evidence/signins.txt" to
                "2026-02-11T08:10Z account=maya result=success source=192.0.2.14\n" +
                "2026-02-11T08:12Z account=leo result=failed source=192.0.2.44\n" +
                "2026-02-11T08:13Z account=leo result=failed source=192.0.2.44\n" +
                "2026-02-11T08:14Z account=leo result=failed source=192.0.2.44\n" +
                "2026-02-11T08:16Z account=amina result=success source=192.0.2.19"),
            listOf("List the evidence directory.", "Read evidence/signins.txt.", "Look for an account appearing in several failed events."),
            "leo", 80
        ),
        Lab(
            "asset-inventory", "Asset inventory check", "Beginner",
            "Find the device that is missing an assigned owner.",
            "The IT team is checking the quality of its fictional asset register. Find the asset whose owner field is marked unassigned.",
            mapOf("inventory/assets.csv" to
                "asset,owner,status\nLT-104,Jordan,managed\nSRV-022,Unassigned,managed\nLT-118,Amira,managed\n"),
            listOf("Read inventory/assets.csv.", "Compare the owner column for each asset.", "Submit the asset identifier, not the owner's name."),
            "SRV-022", 80
        ),
        Lab(
            "alert-context", "Alert context", "Intermediate",
            "Determine which event ID is associated with a disabled test account.",
            "A fictional monitoring export contains several routine events. Find the event ID where the account state is disabled.",
            mapOf("alerts/events.log" to
                "event=EV-210 user=training-a state=active action=login\n" +
                "event=EV-211 user=training-b state=disabled action=login-blocked\n" +
                "event=EV-212 user=training-c state=active action=password-change\n"),
            listOf("Read alerts/events.log.", "Find the line containing state=disabled.", "Submit its event identifier."),
            "EV-211", 120
        ),
        Lab(
            "backup-review", "Backup readiness", "Intermediate",
            "Find the backup job that did not complete successfully.",
            "Review this fictional backup status report. Identify the job with a result other than SUCCESS.",
            mapOf("reports/backup-status.txt" to
                "job=nightly-documents result=SUCCESS\n" +
                "job=finance-archive result=SUCCESS\n" +
                "job=training-db result=FAILED\n" +
                "job=media-library result=SUCCESS\n"),
            listOf("Read reports/backup-status.txt.", "Compare the result field for each job.", "Submit the job name."),
            "training-db", 120
        )
    )

    val tools = listOf(
        ToolGuide("Wireshark", "Traffic analysis", "Helps inspect packet captures to understand network conversations.", "Use supplied captures or networks you are explicitly authorised to monitor."),
        ToolGuide("CyberChef", "Data analysis", "A browser-based workbench for examining and transforming data formats.", "Use it to understand encodings and file formats, not to treat encoding as encryption."),
        ToolGuide("OWASP ZAP", "Web defence", "Supports web application security testing and helps teams identify issues.", "Use training applications or systems covered by written authorisation."),
        ToolGuide("YARA", "Threat research", "Matches files against analyst-authored patterns to support classification.", "Test rules against benign samples and approved research datasets."),
        ToolGuide("Ghidra", "Reverse engineering", "Helps analysts understand compiled programs during software review.", "Analyse software you own or are permitted to examine."),
        ToolGuide("Volatility", "Memory forensics", "Supports structured examination of memory images during investigations.", "Work with consented forensic images and preserve evidence handling notes.")
    )

    val checklist = listOf(
        "Use unique passwords and a trusted password manager",
        "Enable multi-factor authentication where available",
        "Install operating-system and app security updates",
        "Keep a protected backup and test restoring it",
        "Review account recovery options",
        "Lock and encrypt devices when supported",
        "Check links and attachments before opening",
        "Install apps from trusted sources"
    )

    fun lesson(id: String): Lesson? = lessons.firstOrNull { it.id == id }
}
