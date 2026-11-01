---
title: Instructional Design Document
short: ID document
version: Draft 1
---

# Introduction and instructional design approach

TODO: Need input from the team.

# Target learners and assumed prior knowledge

## Intended learners for this application

The intended learners are students preparing for or beginning COS212 (Data Structures and Algorithms) at the University of Pretoria. The University of Pretoria 2026 Computer Science Yearbook [25] describes the programming knowledge covered in COS132, COS151 and COS110. COS132 introduces imperative programming. COS151 introduces algorithms and algorithm modelling. COS110 introduces object-oriented programming and basic data structures, including lists, stacks and queues. These modules provide a foundation for learning graphs and Breadth-First Search (BFS). Our application will build on this knowledge. It will not assume that students already know graphs or BFS. It will introduce these topics before the students attend their COS212 lectures.

## Prerequisites for using this application

### COS132: Imperative Programming

Students are expected to have basic programming knowledge. The University of Pretoria 2026 Computer Science Yearbook [25] states that COS132 covers types, control structures, arrays, functions and libraries. It also teaches students how to create, run and debug programs. The application can use these skills in its coding activities. Students can predict what a short piece of code will do. They can also complete missing lines of code in a BFS implementation. The application should not spend too much time teaching basic programming again. However, it should provide short explanations when students struggle with these concepts.

### COS151: Introduction to computer science

Students are expected to have basic knowledge of computer science and algorithms. The University of Pretoria 2026 Computer Science Yearbook [25] states that COS151 covers algorithms, complexity, Boolean logic, automata theory and algorithm modelling. The application can build on this knowledge when introducing BFS. It can explain the algorithm before showing the Python implementation. Students can first follow the steps using a graph diagram. They can then connect these steps to the code. This will help them understand the logic behind the algorithm.

### COS110: Introduction to program design

Students are expected to have experience with object-oriented programming and basic data structures. The University of Pretoria 2026 Computer Science Yearbook [25] states that COS110 covers modular program design, encapsulation, interfaces, reuse, lists, stacks and queues. The application can build on students' knowledge of queues. BFS uses a queue to determine which vertex must be processed next. However, students may need a reminder of how queues work. The application should explain this connection before students complete BFS activities.

## Distinguishing existing knowledge from new knowledge

The application should build on existing knowledge while teaching graphs and BFS from the beginning. For example, students are expected to know basic programming and queues. They are not expected to know how to present a graph or perform BFS before using the application. They must learn what a graph is, why graphs are useful, what BFS does and how to implement it. This approach will help students connect new concepts to what they already know. It will also prevent the application from spending too much time reteaching prerequisite content. Students will instead focus on the knowledge they need for the selected COS212 topic.

## Identifying potential differences between learners

### Programming knowledge and confidence

Students may have different levels of programming knowledge and confidence. Smith et al. [19] studied prior knowledge in introductory programming courses. Their findings showed that students' self-reported experience and confidence did not always provide the same information as a programming aptitude test. Their study also discussed differences in students' prior programming knowledge. This suggests that the application should not rely only on students' opinions of their own abilities. It should also include short practical tasks. These tasks can test whether students can apply basic programming concepts. The application can then provide suitable support where needed.

### Recall of prerequisite knowledge

Students may not remember all the concepts they learned in their prerequisite modules. A student may remember what a queue is but may have forgotten how to add or remove an item. Another student may understand loops but struggle to apply them in a BFS implementation. The application should include short refresher activities when these concepts are needed. For example, students could complete a single queue exercise before tracing BFS. This will allow them to revise the required knowledge without repeating an entire programming topic.

### Experience with the selected programming language

Students may differ in their experience with the programming language used in the application. The application uses Python to teach graph representation and BFS. Some students may be more familiar with a different programming language. The application should focus on the logic of graphs and BFS rather than treating knowledge of a specific language as proof of algorithmic understanding. A short introduction to the selected language may be useful. Students should then practise translating the algorithm into code. This will help them separate difficulties with programming syntax from difficulties with the algorithm itself.

### Learning pace and familiarity with visual representations

Students may progress through the material at different speeds. They may also differ in how familiar they are with graph diagrams and other visual representations. For example, one student may quickly identify vertices while another may need more examples before understanding how these connections are represented in code. Some students may also need more time to follow the queue during a BFS traversal. The application should allow students to pause, replay and step through the lesson. It should show the graph, queue and visited vertices during the algorithm. Students should also be able to connect the graph diagram to its code representation. These features will help them review difficult steps at their own pace.

## How the learner profile influences the application's design

The application will build on students' existing programming knowledge while providing support when they need it. For example, students will first receive a short explanation of graphs and their purpose. They will then explore vertices and edges in an interactive graph. The application will introduce BFS step by step. Students will be asked to predict the next vertex, update the queue and complete small sections of code. A brief queue refresher will be available before the BFS activities. The design will connect new knowledge to concepts students have already encountered. It will also allow students to practise throughout the lesson instead of only after watching a tutorial. Immediate feedback and hints will help students identify mistakes. Students who understand a concept can continue, while those who struggle can review the explanation and try again. Uhanova et al. [24] studied the relationship between prior programming knowledge, additional practice and academic performance in an introductory programming course. The authors reported better academic performance among students who attended an additional algorithm practice course. They discussed reviewing course content and solving extra problems as possible benefits of this support.

# Measurable learning objectives

## Learning objectives

By the end of the application, students should be able to achieve the following objectives. Each objective begins with an action verb, making it possible to measure their performance.

1. Define and distinguish a data structure, an algorithm, a graph and graph traversal, using an example of each.
2. Identify and explain vertices and edges in a graph and distinguish between directed and undirected graphs.
3. Explain why graphs are useful by matching a real-world problem, such as a network of connected locations, to an appropriate graph representation.
4. Explain the purpose of BFS and identify situations in which graph traversal is useful.
5. Trace BFS manually on a given graph, correctly identifying the next vertex to process, the queue contents, the visited vertices and the traversal order.
6. Implement BFS in Python using the selected graph representation and a queue, producing the expected traversal for a given input.
7. Test and debug a BFS implementation using suitable test cases, including a disconnected graph or a graph containing a cycle.

The learning objectives move from simpler to more complex thinking. Learning objective 1, for example, asks students to define terms, while learning objective 7 asks them to test and debug code. The revised Bloom's taxonomy describes these levels as remember, understand, apply, analyse, evaluate and create [1]. Using the taxonomy helps us choose tasks that match the level of each objective. Table 1 shows the level assigned to each learning objective.

## What counts as successful performance?

Successful performance means meeting a clear criterion for each objective. An effective objective states what the student must do, the conditions under which the task is performed and the required standard [14]. For example, for learning objective 5, a student must trace BFS on a new graph with at most one error. Clear criteria remove guesswork and allow the application to assess every student consistently.

We judge each objective separately instead of giving one overall mark. A student may do well on learning objectives 1 to 4 but fail learning objective 6. One overall mark would hide this problem. Separate results show exactly what to review. This fits mastery learning, where students show that they have learned one step before they move on. A meta-analysis found that mastery learning programmes improved student achievement [12].

Each objective ends in one of three states. "Met independently" means the student met the criterion without needing hint level 3 or 4. "Met with support" means the student met the criterion after using one of those levels. "Not yet" means the student did not meet the criterion. For example, a student who needs the worked solution to write BFS is shown as "Met with support" for objective 6. This separates "can do" from "can do alone". The student sees both. This honest picture helps students decide how much more practice they need.

A student is ready for the lecture when no objective is marked "Not yet". The student does not need every objective to be "Met independently". The lecture will deepen the work. A student with a "Not yet" result is sent to a review path, which Section 7 describes. This meets the requirement that the application gives extra scaffolding to students who need it.

| No. | Level | Evidence the application collects | Criterion for success |
|---|---|---|---|
| 1 | Remember, understand | Matching and multiple-choice items on the key terms. | At least 4 of 5 items correct. |
| 2 | Understand | Labelling vertices and edges on 3 diagrams. Classifying 4 graphs as directed or undirected. | At least 80% of the labels and classifications correct. |
| 3 | Apply | Matching 4 real-world situations to a graph model. The student names the vertices, the edges and the direction. | At least 3 of 4 situations modelled correctly. |
| 4 | Understand | Choosing when BFS is suitable in 4 short scenarios. The student picks the correct reason for each choice. | At least 3 of 4 choices and reasons correct. |
| 5 | Apply | Tracing BFS on an unseen graph of 6 to 8 vertices by filling in a table. | Correct queue, visited set and next vertex at every step, with at most one error. |
| 6 | Apply | Writing BFS in Python on the student's own graph class. | Passes all hidden test cases, including the expected traversal order. |
| 7 | Analyse, evaluate | Fixing 2 faulty versions of BFS. Writing 2 test cases: a disconnected graph and a graph with a cycle. | Both bugs fixed. Both tests are valid and each faulty version fails at least one test. |

Table: Level, evidence and success criterion for each learning objective.

# Instructional design model and its application

An instructional design model is a clear step-by-step guide for creating good learning materials. It helps designers identify what students need, plan lessons, develop content and evaluate its effectiveness. Using an instructional design model gives teachers and designers a structured process for planning and improving learning materials. The aim is to stay organised and ensure that each lesson supports student learning.

## Using the ADDIE instructional model

We use the ADDIE (Analyse, Design, Develop, Implement and Evaluate) model as the core framework for our group project. It guides designers through a structured process of research, planning, lesson development, implementation and evaluation. In our project, each phase creates clear work to share and review, such as a learner profile or lesson plan. Although ADDIE can be linear, we use it as a flexible, repeating cycle so we can quickly fix parts that fail student testing [5]. To save time and avoid late surprises, we also use rapid prototyping inside ADDIE by building and testing early versions of our lessons with a few peers [23]. Overall, this combined approach gives us a clear, proven process that lowers development costs and helps us improve our application quickly before the deadline.

## Applying ADDIE to the COS212 application

Table 2 shows how each phase applies to this project. The software engineering side of the project is described in the SE document. This document describes the learning design. Both documents describe the same prototype.

| Phase | Work in this project | Output | Dates |
|---|---|---|---|
| Analyse | Study the learners, their prior knowledge and the differences between them (Section 2). Check what CS2023 lists for graphs and BFS. | Learner profile | TBD |
| Design | Write the objectives, success criteria, assessments and lesson plan. Choose the motivation and gamification design. | Objectives, assessment plan and storyboards | TBD |
| Develop | Build the lessons, tasks, hints and feedback messages. Write the Python tasks and their test cases. | Working prototype | TBD |
| Implement | Run the prototype with a small group of peers. Fix urgent problems. | Pilot session and usage logs | TBD |
| Evaluate | Collect survey and test results. Review the data and update the design. Finish this document. | Evaluation summary | TBD |

Table: The ADDIE phases applied to the COS212 application.

## Lesson structure using Gagné's nine events

We use Gagné's Nine Events of Instruction as a step-by-step guide to structure all the modules in our application. This framework helps teachers plan and deliver effective lessons by organising learning into nine clear stages [17], such as opening with a short hook and ending with a real-world task. We use this model because it gives us a proven structure so we do not have to invent one under time pressure, while keeping students engaged and ensuring they can apply what they learn. Table 3 shows how the application carries out each event.

| Event | How the application does it |
|---|---|
| 1. Gain attention | A short puzzle on a campus map: "Which building can you reach in the fewest steps?" It appears before any terms are taught. |
| 2. Inform learners of the objectives | Each module starts with "By the end of this module you can …" in plain words. The words match the objectives. |
| 3. Stimulate recall of prior learning | A quick queue refresher that uses COS110 knowledge: add an item, remove an item and first in, first out. |
| 4. Present the content | A narrated walkthrough that shows the graph, the queue and the visited set together. Each segment covers one idea. |
| 5. Provide learning guidance | A worked example first. Then partly completed code. Then a blank task. A four-level hint ladder is always available. |
| 6. Elicit performance | Checkpoints where the student predicts, traces, completes or writes code before the lesson continues. |
| 7. Provide feedback | Instant and specific feedback from trace checks and test cases. The feedback explains why an answer is wrong. |
| 8. Assess performance | A final mastery check with unseen graphs. The result is shown for each objective. |
| 9. Enhance retention and transfer | Opening questions that recall earlier modules. A closing task that applies BFS to a new problem. An optional bonus quest. |

Table: Gagné's nine events applied to the BFS lessons.

## Lesson sequence

The application has seven short modules, each focused on one main idea. This keeps every part small enough to complete in one sitting. The total duration is approximately 75 minutes. Students can stop after any module and the application saves their progress. Table 4 shows each module, the objectives it covers and its activities.

Constructive alignment means that objectives, learning activities and assessment point to the same skill [4]. For example, learning objective 6 asks students to write BFS. So the activity is writing BFS, and the assessment runs the student's code against tests. A multiple-choice question about BFS would not show that a student can write it. The alignment keeps the application honest about what it teaches and what it measures.

| Module | Learning objectives | Main learning activities | Assessment evidence | Duration (minutes) |
|---|---|---|---|---|
| 0. Warm-up and queue refresher | Prior knowledge | Short quiz on queues and basic Python. The application picks the refreshers the student needs. | Diagnostic score | 5 |
| 1. What is a graph? | 1, 2, 3 | Build a campus graph by adding vertices and edges. Classify directed and undirected graphs. Match real situations to graphs. | Labelling and matching checkpoints | 12 |
| 2. A graph in Python | 2, 6 | Complete `add_vertex` and `add_edge` in a `Graph` class. Make the class handle directed and undirected edges. | Code checkpoints with test cases | 10 |
| 3. Meet BFS | 4, 5 | Watch BFS on the campus graph. Predict the next vertex. Fill in the queue, the visited set and the traversal order. | Trace checkpoints | 12 |
| 4. Write BFS | 6 | Put shuffled lines of code in order. Fill in missing lines. Write BFS in a blank function. | Hidden test cases | 15 |
| 5. Test and debug | 7 | Find and fix bugs in faulty BFS code. Write tests for a disconnected graph and for a graph with a cycle. | Bug-fix and test-writing tasks | 10 |
| 6. Mastery check and report | 1–7 | Unseen items on every objective. A report for each objective with next steps. | Criteria in Table 1 | 10 |

Table: The lesson sequence, in which each row links objectives, activities and evidence. This follows constructive alignment [4].

Each checkpoint is small and focused on one key idea. Here is an example from module 2. The lesson explains that an undirected edge must be stored in both directions. The student then completes the method below.

```python
class Graph:
    def __init__(self):
        self.adjacency = {}  # vertex -> list of neighbours

    def add_vertex(self, v):
        if v not in self.adjacency:
            self.adjacency[v] = []

    def add_edge(self, a, b):
        # Connect a and b in both directions.
        ...
```

# Learning theories and instructional rationale

We use four groups of ideas to explain our design: active learning, cognitive load, scaffolding and retrieval practice. Motivation theories appear in Section 7. Table 5 summarises these ideas at the end of this section.

## Active learning

Students learn more when they do something with the content. The ICAP framework ranks learning activities as passive, active, constructive and interactive, and it links deeper activity to deeper learning [6]. A large review of science, engineering and mathematics courses found that active learning raised exam scores and lowered failure rates compared with lectures [8]. Our checkpoints ask students to drag, trace and write code. These are active and constructive tasks. The application cannot offer peer discussion, so the lecture will provide the interactive part.

Active learning does not mean unguided learning. Kirschner, Sweller and Clark argue that minimal guidance works poorly for novices [11]. Our students are new to graphs. For this reason every task is guided. Each task has a worked example before it, small steps and hints. The student is active, but the student is not alone.

Interactive video also supports learning. Zhang and colleagues compared video that let learners control how they moved through it with video that did not. The group with control had better learning results and higher satisfaction [29]. Another study put short tests inside an online lecture. This reduced mind wandering and improved later test results [22]. These findings support our lesson format, which stops for tasks and gives the student control.

## Cognitive load and multimedia design

Working memory is limited, so a lesson must avoid overload. BFS asks a student to track the current vertex, the queue and the visited set at the same time. Sweller showed that novices who solve problems by searching for a method can struggle to build useful knowledge, and that worked examples can help [20]. Later work asks designers to cut load that does not help learning [21]. For this reason each module starts with a worked example. It then moves to partly completed tasks and then to blank tasks.

We also apply Mayer's multimedia principles [15]. We use signalling, which means the current vertex is highlighted in each step. We use segmenting, which means each segment covers one idea and the student controls the pace. We use pre-training, which means the key terms and the queue refresher come before BFS. We use coherence, which means we leave out decoration that does not teach. These choices cut extra load, so students can spend their effort on the algorithm.

Support must also fade as skill grows. Kalyuga and colleagues found that guidance that helps novices can hurt more experienced learners [10]. For example, a confident student may find a long worked example slow and boring. The application therefore lets students skip a refresher or a worked example after they pass a short check. It also offers optional bonus quests for students who want more challenge.

## Scaffolding and the zone of proximal development

Students learn best at the edge of what they can do alone. Vygotsky called the gap between what a learner can do alone and what a learner can do with help the zone of proximal development [27]. A student who cannot write BFS alone may manage it with a partly completed version. Our tasks sit in this gap, and help is always available.

Scaffolding is temporary support that fades. Wood, Bruner and Ross described tutor support such as simplifying the task, keeping the learner focused on the goal and pointing out key features [28]. Van de Pol and colleagues name three features of good scaffolding: it responds to the learner, it fades and it passes responsibility to the learner [26]. Our hint ladder and our move from worked example to blank task follow these features. Module 3 gives a lot of support. Module 5 gives much less.

Computer-based scaffolding works in practice. A meta-analysis of science, technology, engineering and mathematics education found that computer-based scaffolding had a positive effect on learning [3]. This supports the idea that an application can give useful support without a human tutor.

We also use Parsons problems as a step between reading code and writing code. A Parsons problem asks the student to put shuffled lines of code in the right order. Denny, Luxton-Reilly and Simon found that student performance on these problems was highly correlated with performance on code-writing questions [7]. This suggests that the problems test a related skill. The student can focus on the order of the steps and does not have to recall every line of syntax. They are also easy for the application to mark.

## Prior knowledge, retrieval practice and tracing

New ideas stick best when they link to what students already know. Ausubel argued that prior knowledge is the most important influence on learning [2]. Our students know queues from COS110. The warm-up recalls that knowledge, and module 3 then shows that BFS is a queue at work. This links the new idea to a familiar one.

Recalling information strengthens memory. Roediger and Karpicke found that taking memory tests led to better long-term retention than repeated study [18]. For this reason each module opens with one or two questions on earlier modules. This practice helps students remember. It also shows them which ideas are still weak.

Students need to trace code before they can write it well. Lister and colleagues found that many novice programmers could not trace short pieces of code correctly. They suggested that reading and tracing are skills students need before they write code [13]. For this reason students trace BFS by hand in module 3, before they write it in module 4.

Showing BFS on screen helps only if students take part. Hundhausen, Douglas and Stasko found that how students use a visualisation matters more than what it shows [9]. Naps and colleagues reached a similar view. They concluded that visualisations help when they make learners active [16]. For this reason students predict the next vertex before the animation shows it. The animation then confirms or corrects the prediction.

| Theory | Key idea | How the application applies it |
|---|---|---|
| Active learning [6] | Deeper activity leads to deeper learning. | Checkpoints ask students to predict, trace and write code. |
| Cognitive load [21, 15] | Working memory is limited. | Worked examples first. One idea per segment. The graph, queue and visited set shown together. |
| Scaffolding [27, 28] | Support lets students do more than they can alone. It fades over time. | A four-level hint ladder. Parsons problems. Less help in later modules. |
| Retrieval practice [18] | Recalling information strengthens memory. | Opening questions on earlier modules. A final mastery check. |
| Prior knowledge [2] | New ideas link to existing ideas. | A warm-up on queues and basic Python. |

Table: Summary of the learning theories and how the app applies them.

# Learning preferences, accessibility and inclusive design

TODO: Need input from the team.

# Motivation, engagement, assessment, feedback and scaffolding

TODO: Need input from the team.

# Evaluation of learning effectiveness

TODO: Need input from the team.

# Generative AI acknowledgement and prompt record

## Software engineering

**Tool:** Claude Code, Anthropic's coding assistant, using the Claude Opus 5.5 model, run in the software engineers' development environment.

**What it was used for:** drafting and revising the SE document; proposing options for engineering decisions, which the team then made; writing the project's tooling and infrastructure (CI checks, the database layer, deployment on Coolify, the staging login page, the "coming soon" page, the document builder and its PDF format); organising the course material in the repository; and setting up the project board and its backlog.

**How its output was checked:** every change went through a pull request that a team member reviewed, and all code passes the project's automated checks (formatting, linting, type checks, tests and builds). Each decision it proposed was accepted, changed or rejected by the team; the decisions are recorded in the SE document (§2, §15.3).

**Main prompts**, as typed:

| Date | Prompt | Used for |
|---|---|---|
| 31 Oct 2026 | "is cos750 project hosted yet? has my personal coolify api been used to host and add the project" | Hosting the app on Coolify |
| 31 Oct 2026 | "for now the master version should just have a "something great coming soon, until the next deploy to master." | The "coming soon" page on production (GUI) |
| 31 Oct 2026 | "what about the repo now. are tests and linitng rules etc in place?" and "this needs to be enhanced then" | CI checks, tests and linting |
| 31 Oct 2026 | "i think only users with some sort of password should be able to see what is going on in staging" | The staging login page (GUI) |
| 1 Nov 2026 | "as a software engineer based on the spec what am i supposed to be doing" | Planning the SE work against the specification |
| 1 Nov 2026 | "i haved dumpped all of the course material into the docs folder, orgnaize all of this. as this will be what the project is based on" | Organising the course material and its index |
| 1 Nov 2026 | "look over it and see if we discagree on anything? or if anything is missing." | Reviewing SE document draft 1 |
| 1 Nov 2026 | "lets get the techstack matching what weve built unless there is a good reason to do it her way." | SE document: technology stack |
| 1 Nov 2026 | "lets start on the next missing section. what are the choices i have to make here?" | SE document: methodology options |
| 1 Nov 2026 | "i think we need to include these docs in the repo. and md files, this is what the team will work with, but we will have a script that generates pdfs in a standard format" | The document builder and PDF format |
| 1 Nov 2026 | "okay, for the se doc, what is the next thing we need to add/ make desisions on or correct" | SE document: alignment with this document |
| 1 Nov 2026 | "yes lets carry on with the nes things we need to do in the se doc. ask me questions if the asnswer requires inout" | SE document: testing strategy and diagrams |
| 1 Nov 2026 | "okay lets continue building it. ask me questions you need imput on" | SE document: stakeholders, wireframes, references; the Sprint 0 record |

Table: Generative AI prompts for the software engineering work.

## Instructional design

TODO: The instructional design team adds the tools and prompts used for this document and for the app's content.

# References and supporting evidence

<div class="references">

[1] Lorin W. Anderson and David R. Krathwohl, editors. *A Taxonomy for Learning, Teaching, and Assessing: A Revision of Bloom's Taxonomy of Educational Objectives.* Longman, New York, NY, 2001. Accessed: 2026-10-28.

[2] David P. Ausubel. *Educational Psychology: A Cognitive View.* Holt, Rinehart and Winston, New York, NY, 1968.

[3] Brian R. Belland, Andrew E. Walker, Nam Ju Kim, and Mason Lefler. Synthesizing results from empirical research on computer-based scaffolding in STEM education: A meta-analysis. *Review of Educational Research*, 87(2):309–344, 2017.

[4] John Biggs. Enhancing teaching through constructive alignment. *Higher Education*, 32(3):347–364, 1996. Accessed: 2026-10-28.

[5] Robert Maribe Branch. *Instructional Design: The ADDIE Approach.* Springer, New York, NY, 2009. Accessed: 2026-10-28.

[6] Michelene T. H. Chi and Ruth Wylie. The ICAP framework: Linking cognitive engagement to active learning outcomes. *Educational Psychologist*, 49(4):219–243, 2014.

[7] Paul Denny, Andrew Luxton-Reilly, and Beth Simon. Evaluating a new exam question: Parsons problems. In *Proceedings of the Fourth International Workshop on Computing Education Research (ICER '08)*, pages 113–124, New York, NY, USA, 2008. ACM.

[8] Scott Freeman, Sarah L. Eddy, Miles McDonough, Michelle K. Smith, Nnadozie Okoroafor, Hannah Jordt, and Mary Pat Wenderoth. Active learning increases student performance in science, engineering, and mathematics. *Proceedings of the National Academy of Sciences*, 111(23):8410–8415, 2014.

[9] Christopher D. Hundhausen, Sarah A. Douglas, and John T. Stasko. A meta-study of algorithm visualization effectiveness. *Journal of Visual Languages & Computing*, 13(3):259–290, 2002.

[10] Slava Kalyuga, Paul Ayres, Paul Chandler, and John Sweller. The expertise reversal effect. *Educational Psychologist*, 38(1):23–31, 2003.

[11] Paul A. Kirschner, John Sweller, and Richard E. Clark. Why minimal guidance during instruction does not work: An analysis of the failure of constructivist, discovery, problem-based, experiential, and inquiry-based teaching. *Educational Psychologist*, 41(2):75–86, 2006.

[12] Chen-Lin C. Kulik, James A. Kulik, and Robert L. Bangert-Drowns. Effectiveness of mastery learning programs: A meta-analysis. *Review of Educational Research*, 60(2):265–299, 1990.

[13] Raymond Lister, Elizabeth S. Adams, Sue Fitzgerald, William Fone, John Hamer, Morten Lindholm, Robert McCartney, Jan Erik Moström, Kate Sanders, Otto Seppälä, Beth Simon, and Lynda Thomas. A multi-national study of reading and tracing skills in novice programmers. *ACM SIGCSE Bulletin*, 36(4):119–150, 2004.

[14] Robert F. Mager. *Preparing Instructional Objectives: A Critical Tool in the Development of Effective Instruction.* CEP Press, Atlanta, GA, 3rd edition, 1997.

[15] Richard E. Mayer. *Multimedia Learning.* Cambridge University Press, Cambridge, UK, 2nd edition, 2009.

[16] Thomas L. Naps, Guido Rößling, Vicki Almstrum, Wanda Dann, Rudolf Fleischer, Chris Hundhausen, Ari Korhonen, Lauri Malmi, Myles McNally, Susan Rodger, and J. Ángel Velázquez-Iturbide. Exploring the role of visualization and engagement in computer science education. *ACM SIGCSE Bulletin*, 35(2):131–152, 2003. Report of the ITiCSE 2002 working group.

[17] Northern Illinois University Center for Innovative Teaching and Learning. Gagné's nine events of instruction. <https://www.niu.edu/citl/resources/guides/instructional-guide/gagnes-nine-events-of-instruction.shtml>, 2020. Accessed: 2026-10-28.

[18] Henry L. Roediger and Jeffrey D. Karpicke. Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science*, 17(3):249–255, 2006.

[19] David H. Smith IV, Qiang Hao, Filip Jagodzinski, Yan Liu, and Vishal Gupta. Quantifying the effects of prior knowledge in entry-level programming courses. In *Proceedings of the ACM Global Computing Education Conference 2019 (CompEd '19)*, pages 30–36, New York, NY, USA, 2019. ACM. Accessed: 2026-10-28.

[20] John Sweller. Cognitive load during problem solving: Effects on learning. *Cognitive Science*, 12(2):257–285, 1988.

[21] John Sweller, Jeroen J. G. van Merriënboer, and Fred G. W. C. Paas. Cognitive architecture and instructional design. *Educational Psychology Review*, 10(3):251–296, 1998.

[22] Karl K. Szpunar, Novall Y. Khan, and Daniel L. Schacter. Interpolated memory tests reduce mind wandering and improve learning of online lectures. *Proceedings of the National Academy of Sciences*, 110(16):6313–6317, 2013.

[23] Steven D. Tripp and Barbara Bichelmeyer. Rapid prototyping: An alternative instructional design strategy. *Educational Technology Research and Development*, 38(1):31–44, 1990. Accessed: 2026-10-28.

[24] Marina Uhanova, Natalya Prokofyeva, Sabina Katalnikova, Oksana Zavjalova, and Viktorija Ziborova. The influence of prior knowledge and additional courses on the academic performance of students in the introductory programming course CS1. *Procedia Computer Science*, 225:1397–1406, 2023. Accessed: 2026-10-28.

[25] University of Pretoria. *University of Pretoria Yearbook 2026: BSc in Computer Science*, 2026. Accessed: 2026-10-28.

[26] Janneke van de Pol, Monique Volman, and Jos Beishuizen. Scaffolding in teacher–student interaction: A decade of research. *Educational Psychology Review*, 22(3):271–296, 2010.

[27] Lev S. Vygotsky. *Mind in Society: The Development of Higher Psychological Processes.* Harvard University Press, Cambridge, MA, 1978.

[28] David Wood, Jerome S. Bruner, and Gail Ross. The role of tutoring in problem solving. *Journal of Child Psychology and Psychiatry*, 17(2):89–100, 1976.

[29] Dongsong Zhang, Lina Zhou, Robert O. Briggs, and Jay F. Nunamaker. Instructional video in e-learning: Assessing the impact of interactive video on learning effectiveness. *Information & Management*, 43(1):15–27, 2006.

</div>
