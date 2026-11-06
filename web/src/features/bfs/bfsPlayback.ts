export type PlaybackPhase = 'ready' | 'answering' | 'feedback'

export type PredictionFeedback = {
  selected: string
  correct: boolean
  expected: string
}

export type PlaybackState = {
  frameIndex: number
  lastFrameIndex: number
  phase: PlaybackPhase
  predictionMode: boolean
  playing: boolean
  speedMs: number
  feedback: PredictionFeedback | null
}

export type PlaybackAction =
  | { type: 'REQUEST_NEXT'; predictionRequired: boolean }
  | { type: 'ANSWER'; feedback: PredictionFeedback }
  | { type: 'CONTINUE' }
  | { type: 'BACK' }
  | { type: 'RESET' }
  | { type: 'TOGGLE_PLAY' }
  | { type: 'SET_SPEED'; speedMs: number }
  | { type: 'SET_PREDICTION_MODE'; enabled: boolean }

export function createPlayback(input: { frameCount: number }): PlaybackState {
  return {
    frameIndex: 0,
    lastFrameIndex: Math.max(0, input.frameCount - 1),
    phase: 'ready',
    predictionMode: true,
    playing: false,
    speedMs: 900,
    feedback: null,
  }
}

function advance(state: PlaybackState): PlaybackState {
  if (state.frameIndex === state.lastFrameIndex) return state

  return {
    ...state,
    frameIndex: state.frameIndex + 1,
    phase: 'ready',
    feedback: null,
  }
}

function cancelPrompt(state: PlaybackState): PlaybackState {
  return { ...state, phase: 'ready', feedback: null, playing: false }
}

export function playbackReducer(
  state: PlaybackState,
  action: PlaybackAction,
): PlaybackState {
  switch (action.type) {
    case 'REQUEST_NEXT':
      if (state.phase !== 'ready' || state.frameIndex === state.lastFrameIndex) return state
      if (!action.predictionRequired) return advance(state)
      return { ...state, phase: 'answering', playing: false }

    case 'ANSWER':
      return { ...state, phase: 'feedback', playing: false, feedback: action.feedback }

    case 'CONTINUE':
      return state.phase === 'feedback' ? advance(state) : state

    case 'BACK':
      if (state.phase !== 'ready') return cancelPrompt(state)
      return {
        ...state,
        frameIndex: Math.max(0, state.frameIndex - 1),
        playing: false,
        feedback: null,
      }

    case 'RESET':
      return {
        ...state,
        frameIndex: 0,
        phase: 'ready',
        playing: false,
        feedback: null,
      }

    case 'TOGGLE_PLAY':
      if (state.phase !== 'ready' || state.frameIndex === state.lastFrameIndex) return state
      return { ...state, playing: !state.playing }

    case 'SET_SPEED':
      return { ...state, speedMs: action.speedMs }

    case 'SET_PRODICTION_MODE':
      return { ...state, predictionMode: action.enabled }

    default:
      return state
  }
}
