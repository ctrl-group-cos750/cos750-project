# Course material

The COS750 lectures and readings from ClickUP (2026), one folder per lecture. This is what the
SE document, the ID document and the app are built on: when a document makes a design choice, it
should point back to the lecture or paper here that justifies it.

The spec is in [`../spec/`](../spec/). CS2023, which the spec and L07/L08 use, is in
[`../references/kumar-2024-cs2023.pdf`](../references/kumar-2024-cs2023.pdf) and is not repeated
here.

## Where to look

| Writing about | Read |
|---|---|
| Which SE methodology we follow | [L11](l11-lifecycles/) slides 4–11: lifecycle stages; Waterfall, V-model, Spiral, Iterative, Incremental, Prototyping, XP, Agile |
| Which ID model we follow | [L11](l11-lifecycles/) slides 12–37: Gagné's nine events, Merrill's principles, Dick & Carey, Smith & Ragan, ADDIE (worked COS212 example on slide 32), ASSURE, Pebble in a Pond, SAM |
| Learning theories the app applies | [L01](l01-learning-theories/) and its readings: behaviourism, cognitivism, constructivism, information processing, social cognitive, transformative |
| Learning styles the app caters for | [L04](l04-learning-styles/): Curry's onion, VARK, Kolb, Honey & Mumford, VAK |
| Keeping the student motivated | [L05](l05-motivation/): N-Ach vs fear of failure, intrinsic vs extrinsic, flow, Malone & Lepper |
| Interface and interaction design | [L06](l06-user-experience/): human senses, memory (STM/LTM), user classes, dialogue styles, interface types |
| The assessment and the extra scaffolding | [L07](l07-assessment/): learning outcomes, constructive alignment, revised Bloom, assessment criteria and plans, formative vs summative |
| Why graphs + BFS, and at what level | [L08](l08-computing-curricula/) and CS2023's AL knowledge area (skill levels follow an adapted Bloom) |
| What kind of educational software this is | [L09](l09-educational-software/): educational software taxonomy |
| How it could fit UP's systems | [L10](l10-administrative-software/): ERP, CMS, LMS (ClickUP is Blackboard Ultra), LTI, SCORM, xAPI |

## Contents

### [L01 – Learning theories](l01-learning-theories/)

`l01-learning-theories.pdf`: definitions of learning, the main theories, and the jigsaw activity
used in lectures 2–3 (Assignment 1).

`readings/` are the jigsaw readings, excerpts from Schunk (2012) except the transformative
learning ones (Wikipedia). The first number is the ClickUP paper ID; `partN` is the order within
the chapter.

| ID | Theory | Source |
|---|---|---|
| 1.1–1.3 | Behaviourism | Schunk, ch. 3 |
| 2.1–2.2 | Cognitive learning processes | Schunk, ch. 7 |
| 3.1–3.3 | Constructivism | Schunk, ch. 6 |
| 4.1–4.3 | Information processing | Schunk, ch. 5 |
| 5.1–5.3 | Social cognitive theory | Schunk, ch. 4 |
| 6.1–6.3 | Transformative learning | Wikipedia |

Paper 2.3 on ClickUP is the same file as 2.1, so it is not repeated.

### [L04 – Learning styles](l04-learning-styles/)

- `l04-learning-styles.pdf` (13 Aug 2026): definitions, families of models, assessment methods.
- `honey-mumford-learning-styles-questionnaire.pdf`, `vak-learning-styles-questionnaire.pdf`: the two
  self-assessment questionnaires.

### [L05 – Motivation](l05-motivation/)

- `l05-motivation.pdf`: need to achieve vs need to avoid failure, intrinsic vs extrinsic
  motivation, flow (clear goals, immediate feedback, challenge matched to skill), Malone and
  Lepper's framework.
- `malone-lepper-1987-making-learning-fun.pdf`: T. W. Malone and M. R. Lepper, "Making Learning
  Fun: A Taxonomy of Intrinsic Motivations for Learning", 1987. A scan, so the text can't be searched.

### [L06 – User experience](l06-user-experience/)

- `l06-user-experience-interaction.pdf` (27 Aug 2026): human senses, the information processing
  model, short- and long-term memory, user classification, dialogue styles and their desirable
  characteristics, interface types.
- `interface-types/`: the 15 papers for Assignment 2. Each group presented one, so the number
  is the ClickUP paper number.
- `general/`: Schunk's full textbook (the source of the L01 readings), and Yu et al. (2026) on
  memory for LLM agents.

| # | Paper |
|---|---|
| 01 | D. Sonntag, "Intuition as Instinctive Dialogue", 2009 |
| 02 | Y. Lan et al., "Survey of Natural Language Processing for Education: Taxonomy, Systematic Review, and Future Trends", *IEEE TKDE* 38(1), 2026 |
| 03 | O. Shaer and E. Hornecker, "Tangible User Interfaces: Past, Present, and Future Directions", *Foundations and Trends in HCI* 3(1–2), 2010 |
| 04 | M. Weigel, V. Mehta and J. Steimle, "More Than Touch: Understanding How People Use Skin as an Input Surface for Mobile Computing", CHI 2014 |
| 05 | I. V. Osipov, "Transreality puzzle as new genres of entertainment technology", 2017 |
| 06 | C. T. Vi et al., "Gustatory Interface: The Challenges of 'How' to Stimulate the Sense of Taste", 2017 |
| 07 | Y. Lei et al., "O&O: A DIY toolkit for designing and rapid prototyping olfactory interfaces", CHI 2022 |
| 08 | A. M. Al-Ansi et al., "Analyzing augmented reality (AR) and virtual reality (VR) recent development in education", *Social Sciences & Humanities Open* 8, 2023 |
| 09 | V. Hulusic et al., "Tangible User Interfaces for Enhancing User Experience of Virtual Reality Cultural Heritage Applications for Utilization in Educational Environment", *ACM JOCCH*, 2023 |
| 10 | P. B. Perera et al., "Integrating Force Sensing with Electro-Tactile Feedback in 3D Printed Haptic Interfaces", 2024 |
| 11 | N. Tzimos et al., "Multimodal Interaction with Haptic Interfaces on 3D Objects in Virtual Reality", *Electronics* 14, 4035, 2025 |
| 12 | K. A. Mills, A. Brown and C. Moro, "Virtual and augmented reality text environments support self-directed multimodal reading", *Interactive Learning Environments*, 2025 |
| 13 | J. Brown, F. Bello and L. Jones, "A Multimodal Haptic Interface for Simultaneous Softness and Thermal Modulation", EuroHaptics 2026 |
| 14 | F. Tener and J. Lanir, "Guiding, Not Driving: Design and Evaluation of a Command-Based User Interface for Teleoperation of Autonomous Vehicles", *IJHCI*, 2026 |
| 15 | A. K. Orphanides and C. S. Nam, "Touchscreen interfaces in context: A systematic review of research into touchscreens across settings, populations, and implementations", *Applied Ergonomics*, 2017 |

General: D. H. Schunk, *Learning Theories: An Educational Perspective*, 6th ed., Pearson, 2012.
Y. Yu et al., "Agentic Memory: Learning Unified Long-Term and Short-Term Memory Management for
Large Language Model Agents", ACL 2026.

### [L07 – Assessment](l07-assessment/)

- `l07-assessment-evaluation.pdf` (3 Sep 2026): why we assess, learning outcomes
  (`<action verb><topic><mastery>`, 5 to 8 of them), constructive alignment, revised Bloom,
  assessment criteria with pass and differentiated descriptors, formative vs summative,
  assessment in the age of AI.
- `blooms-revised-taxonomy-handout.pdf`: the cognitive process dimension with verbs per level.
- `papers/`:

| # | Paper |
|---|---|
| 1 | C. W. Starr, B. Manaris and R. H. Stalvey, "Bloom's Taxonomy Revisited: Specifying Assessable Learning Objectives in Computer Science", SIGCSE 2008 |
| 2 | E. Thompson, A. Luxton-Reilly, J. L. Whalley et al., "Bloom's Taxonomy for CS Assessment", ACE 2008 (CRPIT 78) |
| 3 | A. Petersen, M. Craig and D. Zingaro, "Reviewing CS1 Exam Question Content", SIGCSE 2011 |
| 4 | L. Fritz, "Effective Assessment for Early Courses in Computer Science: Instruments Other Than Out-of-Class Programming Assignments", *Journal of Instructional Research* 8(2), 2019 |
| 5 | R. Vivian, D. Franklin, D. Frye et al., "Evaluation and Assessment Needs of Computing Education in Primary Grades", ITiCSE 2020 |
| 6 | J. Stanja, W. Gritz, J. Krugel, A. Hoppe and S. Dannemann, "Formative assessment strategies for students' conceptions: The potential of learning analytics", *BJET* 54, 58–75, 2023 |

### [L08 – Computing curricula](l08-computing-curricula/)

- `l08-computing-curricula.pdf`: the history from Curriculum 68 to CS2023, the CS2023 "sunflower"
  model (CS core and KA core), adapted Bloom skill levels, and building a curriculum in the SA context.
- The curricula themselves: `acm-1968-curriculum-68.pdf`, `tucker-1991-computing-curricula-1991.pdf`
  (summary), `acm-ieee-2013-cs2013.pdf`, `cc2020-task-force-2020-computing-curricula-2020.pdf`.
  CS2023 is in `../references/`.

### [L09 – Educational software](l09-educational-software/)

`l09-educational-software.pdf` (1 Oct 2026): what educational software is, its history, and
building a taxonomy of it (ClickUP discussion board).

### [L10 – Software for administration](l10-administrative-software/)

`l10-educational-software-for-administration.pdf`: ERP, CMS and LMS in higher education, LMS
integration standards (REST, webhooks, SCORM, xAPI, cmi5, LTI) and UP's own setup (PeopleSoft,
the UP portal, ClickUP on Blackboard Ultra).

### [L11 – Software and instructional design lifecycles](l11-lifecycles/)

`l11-software-and-instructional-design-lifecycles.pdf`: the lecture the SE and ID documents rest
on most. It covers SE lifecycle stages and methodologies, what instructional design is, Gagné and
Merrill, the ID models (with ADDIE worked through for a COS212 app), and how SAM compares
to agile. It ends by asking "Are SE and ID so different?"

## Not in the repo

The jigsaw group allocations (L01) and the Assignment 2 group list (L06) list every student's
name and student number, so they stay on ClickUP.

## Adding material

Put it in the lecture's folder, named like the rest (lowercase, hyphens), and add a line here.
New lectures get a new `lNN-<topic>/` folder.
