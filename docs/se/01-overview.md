# Overview & Purpose

> **Scope of this document:** Software engineering only. Instructional-design content (learning theories, learning styles, motivation, pedagogy) is deliberately excluded and lives in the separate ID document.

> **DRAFT 1 NOTICE.** Scope is intentionally open. Sections or decisions that are provisional and expected to change are tagged **[PROVISIONAL]**. Items requiring a decision are collected in §13.

## Purpose
The COS212 app is a pre-lecture, tutor-style learning application that teaches **one data structure (Graphs)** and **one algorithm (Breadth-First Search)**. It is used by a student **before** attending the corresponding lecture and assumes **zero prior knowledge** of the topic.

From an engineering standpoint, the system is a web application composed of:
- a **Python backend** that computes BFS traversals, serves content, manages user accounts, tracks scoring/progress, and exposes a REST API;
- a **TypeScript + React frontend** that renders interactive video, interactive graph visualizations, assessments, and a leaderboard;
- a **persistent data store** holding users, content, progress events, scores, and assessment results.

## Engineering goals
- Deterministic, inspectable BFS step generation suitable for front-end animation.
- Clear client/server separation over a documented REST API.
- Persistent user accounts and progress to support gamification (points + leaderboard).
- A content system that can deliver the same lesson concept in multiple modes (video, text, interactive) without code changes per lesson.
- An assessment subsystem whose branching (adaptive scaffolding) is driven by data/config rather than hard-coded logic where practical.

## Primary user & session shape
A single primary role for Draft 1: **Student**. A secondary **Content author/admin** role is noted but out of scope for Draft 1 (§2.2). A typical session: authenticate → work through a lesson (video + text + interactive) → answer embedded questions → step through a BFS visualization → take an assessment → receive scaffolding if needed → see points and leaderboard position.
