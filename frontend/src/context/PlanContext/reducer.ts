import { State, Actions, ActionTypes } from "./types";

export default function planReducer(state: State, action: Actions): State {
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
    case ActionTypes.VERSION_CURRENT: {
      return {
        ...state,
        currentPlanVersion: action.payload,
      };
    }
    case ActionTypes.VERSION_REPLACEMENT: {
      return {
        ...state,
        replacementPlanVersion: action.payload,
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
    case ActionTypes.SET_NAME: {
      return {
        ...state,
        experimentName: action.payload,
      };
    }
    case ActionTypes.SET_RANGE: {
      return {
        ...state,
        dateRange: action.payload,
      };
    }
    default: {
      throw new Error(`Unhandled action type: ${action.type}`);
    }
  }
}
