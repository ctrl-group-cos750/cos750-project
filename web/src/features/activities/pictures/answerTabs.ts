import type { Activity, AttemptResult, Submission } from '../activities.types.ts'
import { answerDrawing, classificationDrawing, correctDrawing } from './drawing.ts'
import type { PictureTab } from './PicturePanel.tsx'
import { pictureName, type ActivityPictures, type Picture } from './pictures.ts'
import { CLASSIFY } from './situations.ts'

export type AnswerView = { tabs: PictureTab[]; caption: string }

/**
 * The tabs that replace a question's picture once the student has an answer checked (#155).
 *
 * After a wrong answer: "Your graph | <the situation>". The correct graph is not shown yet, so the
 * retry still counts. After a right answer or once hint 4 is open (`compare`): "Your graph |
 * Correct graph". Undefined while there is nothing of the student's to draw.
 */
export function answerView(
  activity: Activity,
  pictures: ActivityPictures,
  submitted: Submission | undefined,
  result: AttemptResult | undefined,
  compare: boolean,
): AnswerView | undefined {
  if (!result || !submitted || activity.kind !== 'matching' || !('pairs' in submitted)) return
  const pairs = submitted.pairs
  const situationTab = { name: pictureName(pictures.picture), picture: pictures.picture }

  if (pictures.situation) {
    const situation = pictures.situation
    const graphShaped = situation.link === 'walkway'
    const yours: Picture = {
      kind: 'drawing',
      name: graphShaped ? 'Your graph' : 'Your answers',
      drawing: answerDrawing(activity, situation, pairs, false),
    }
    const yourTab = { name: graphShaped ? 'Your graph' : 'Your answers', picture: yours }
    if (compare) {
      const correct: Picture = {
        kind: 'drawing',
        name: 'Correct graph',
        drawing: correctDrawing(activity, situation, pairs),
      }
      return {
        tabs: [yourTab, { name: 'Correct graph', picture: correct }],
        caption: `${yourTab.name} beside the correct graph. A ${situation.link} you missed is marked in green.`,
      }
    }
    return {
      tabs: [yourTab, situationTab],
      caption: `${yourTab.name}, drawn from your answer. Switch to the ${situationTab.name.toLowerCase()} to compare.`,
    }
  }

  if (pictures.classify) {
    const wrongRows = activity.config.left.filter((item, index) => {
      const part = result.parts.find((p) => p.ref === index)
      const chosen = pairs[item.id]
      return part && !part.correct && (chosen === 'directed' || chosen === 'undirected')
    })
    if (wrongRows.length === 0) return
    const items = wrongRows.flatMap((item) => {
      const row = CLASSIFY[item.id]
      const chosen = pairs[item.id] as 'directed' | 'undirected'
      if (!row) return []
      const meaning = row.meaning[chosen]
      return [
        {
          caption: `${row.picture.name}, if it were ${chosen}: ${meaning}`,
          picture: {
            kind: 'drawing',
            name: row.picture.name,
            drawing: classificationDrawing(row.situation, chosen, row.picture.name, meaning),
          } satisfies Picture,
        },
      ]
    })
    return {
      tabs: [
        { name: 'Your answer', picture: { kind: 'grid', name: 'Your answer', items } },
        situationTab,
      ],
      caption: 'What your answer would mean, drawn. Switch to the four graphs to compare.',
    }
  }
  return
}
