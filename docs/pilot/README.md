# Pilot kit (10 and 11 November)

The team pilots the app on staging before the feature freeze (SE document §14.5, NFR-U4; ID
document §8.2, the Implement phase of ADDIE). Each member works through the modules they did not
build, from a new account, thinking aloud while another member takes notes, then completes the
survey. The results feed the write-up in both documents (#76).

| File | What it is |
|---|---|
| [survey.md](survey.md) | Every survey question, ready to copy into a form, with how to score it |
| [think-aloud-sheet.md](think-aloud-sheet.md) | The note-taker's sheet, one per session |

## Before the first session

- [ ] Every module a participant will pilot has content on staging. A module with no segments
      can't be completed, so the modules after it stay locked (#122).
- [ ] Students can answer activities on staging (the activity pages, #106 and #114).
- [ ] The app records time per module. ID document §8.4 compares it with the planned time, but on
      8 November nothing did: the API accepts `segment_viewed` events (#110), but the module page
      doesn't send them, no `module_completed` event is logged, and module progress keeps only
      when a module was completed, not when it was started. Until it does, the survey's time
      question is the only source.
- [ ] The survey is set up as a form from [survey.md](survey.md), and its link is shared with
      the team.
- [ ] One team member has a staff account to download the pilot data afterwards (see below).
- [ ] Participant codes are handed out (see below).

## Who pilots what

Members pilot only the modules they did not build:

| Module | Built by |
|---|---|
| 0. Warm-up and queue refresher | Ayanda Juqu (#26) |
| 1. What is a graph? | Mohtashim Hussain (#83) |
| 2. A graph in Python | Mohtashim Hussain (#84) |
| 3. Meet BFS | Mohtashim Hussain (#27) |
| 4. Build BFS | Mohtashim Hussain (#85) |
| 5. Test and debug | Simphiwe Nhlapo (#86) |
| 6. Mastery check and report | Mohtashim Hussain (#28) |

A session is about 75 minutes of modules, plus 10 minutes for the survey. In each pair, the two
members take turns: one pilots while the other takes notes, then they swap. Times are for the team
to fill in.

| Participant | Pilots modules | Note-taker | Day and time |
|---|---|---|---|
| Matthew Els | 0–6 | Reece Schmidt | |
| Reece Schmidt | 0–6 | Matthew Els | |
| Ayanda Juqu | 1–6 | Jacobus Hoogenboezem | |
| Jacobus Hoogenboezem | 0–6 | Ayanda Juqu | |
| Joshua Wereley | 0–6 | Simphiwe Nhlapo | |
| Simphiwe Nhlapo | 0–4, 6 | Joshua Wereley | |
| Mohtashim Hussain | 0, 5 | Jacobus Hoogenboezem | |

Modules unlock in order, so nobody can skip one: a module opens only once the one before it is
complete. A participant goes through their own modules quickly, without thinking aloud, and the
note-taker doesn't record them. Ayanda does this for module 0, Simphiwe for module 5, and Mohtashim
for modules 1 to 4 on the way to module 5, so his session is still close to full length.

## Accounts and participant codes

- Each participant **registers a new account** on staging for their session. Not a demo account
  (`@demo.example.com`), and not a staff account: the pilot data page and its CSV files leave both
  out, so their answers wouldn't be counted.
- Each participant gets a code, **P1 to P7**, and gives only that code in the survey, never their
  name. One member keeps a private list of which code is which account's email, so the survey can
  be joined to the pilot data. The list is never committed or shared outside the team.
- After the pilot, the data identifies students by an internal id only (SE document FR-10.3).

## Running a session

1. The participant opens staging in a private browser window and registers their pilot account.
2. The note-taker reads the instructions at the top of the think-aloud sheet aloud, then starts
   the timer.
3. The participant works through their modules, thinking aloud. The note-taker writes, and only
   steps in after two minutes stuck, noting that they did.
4. At the end, the participant fills in the survey with their code. The note-taker files each
   defect as a `bug` issue on the board, linking the sheet.

## After the pilot

- A team member with a staff account downloads the four CSV files from the staff portal's pilot
  data page (`/staff/pilot`): attempts, hints, events and objective results. To make an account
  staff, in the api container's terminal on Coolify: `python -m app.staff grant <email>`.
- The survey responses are exported from the form.
- The analysis follows ID document §8.4; the write-up is #76.
