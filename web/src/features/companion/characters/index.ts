// The five study companion characters (#214). Original 2D drawings, themed on the course.
import './characters.css'
import type { ComponentType } from 'react'
import { Inka } from './Inka.tsx'
import { Juno } from './Juno.tsx'
import type { CharacterProps } from './parts.tsx'
import { Rook } from './Rook.tsx'
import { Rowan } from './Rowan.tsx'
import { Sol } from './Sol.tsx'

export type { CharacterProps, Pose } from './parts.tsx'

export type CompanionId = 'inka' | 'rowan' | 'juno' | 'sol' | 'rook'

export type Character = {
  id: CompanionId
  name: string
  what: string
  Drawing: ComponentType<CharacterProps>
}

/** In the order the profile offers them; Inka, the default, first. */
export const CHARACTERS: readonly Character[] = [
  { id: 'inka', name: 'Inka', what: 'an octopus whose arms are edges', Drawing: Inka },
  { id: 'rowan', name: 'Rowan', what: 'a fox explorer with a map', Drawing: Rowan },
  { id: 'juno', name: 'Juno', what: 'a friendly robot', Drawing: Juno },
  { id: 'sol', name: 'Sol', what: 'a scout with a lantern', Drawing: Sol },
  { id: 'rook', name: 'Rook', what: 'a raccoon tinkerer with a tool belt', Drawing: Rook },
]

export function character(id: CompanionId): Character {
  return CHARACTERS.find((c) => c.id === id) ?? CHARACTERS[0]
}
