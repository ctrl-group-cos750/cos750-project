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
