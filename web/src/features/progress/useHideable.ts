import { useState } from 'react'
import { useRewards, useRewardsSettings } from '../rewards/hooks.ts'
import { usePreference, type Preference } from './preferences.ts'

/** A switch the student can turn off where the element is (#214): `hide` turns it off and
 * remembers that it was turned off here, so the element's place shows `HiddenNote` (with Undo)
 * instead of nothing. */
export function useHideable(name: Preference) {
  const [on, set] = usePreference(name)
  const [hiddenHere, setHiddenHere] = useState(false)
  return {
    on,
    justHidden: hiddenHere && !on,
    hide: () => {
      set(false)
      setHiddenHere(true)
    },
    undo: () => {
      set(true)
      setHiddenHere(false)
    },
  }
}

/** The same for points and badges, which are kept on the account (FR-9.5). */
export function useHideableRewards() {
  const rewards = useRewards()
  const settings = useRewardsSettings()
  const [hiddenHere, setHiddenHere] = useState(false)
  const on = rewards.data?.hideRewards === false
  return {
    on,
    justHidden: hiddenHere && rewards.data?.hideRewards === true,
    hide: () => settings.mutate({ hideRewards: true }, { onSuccess: () => setHiddenHere(true) }),
    undo: () => settings.mutate({ hideRewards: false }, { onSuccess: () => setHiddenHere(false) }),
  }
}
