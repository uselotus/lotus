import { PlanType } from "../../types/plan-type";

export enum ActionTypes {
  SET_CURRENT = "set_current_plan",
  SET_REPLACEMENT = "set_replacement_plan",
  SET_SUBSTITUTION_CALLBACK = "set_substitution_callback",
  INIT = "init",
}

export type State = {
  currentPlan: PlanType | null;
  replacementPlan: PlanType | null;
  onSubstitutionChange: () => void | null;
};

export type Actions = {
  type: ActionTypes;
  payload?: unknown;
};

export type ActionCreators = {
  setCurrentPlan: (data: PlanType) => void;
  setReplacementPlan: (data: PlanType) => void;
  setOnSubstitutionChangeFn: <T>(data: T) => void;
  init: () => void;
};
