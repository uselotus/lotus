import { State, Actions, ActionTypes } from "./types";

export default function planReducer(state: State, action: Actions) {
  switch (action.type) {
    case ActionTypes.SET_CURRENT: {
      return {
        ...state,
        currentPlan: action.payload,
      };
    }
    case ActionTypes.SET_REPLACEMENT: {
      return {
        ...state,
        replacementPlan: action.payload,
      };
    }
    case ActionTypes.SET_SUBSTITUTION_CALLBACK: {
      return {
        ...state,
        onSubstitutionChange: action.payload,
      };
    }
    case ActionTypes.INIT: {
      // NOTE: We can handle persisted data here, like from localStorage
      return {
        ...state,
      };
    }
    default: {
      throw new Error(`Unhandled action type: ${action.type}`);
    }
  }
}
