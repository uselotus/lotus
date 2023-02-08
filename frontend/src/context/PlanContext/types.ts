/* eslint-disable no-shadow */
import { PlanType, PlanVersionType } from "../../types/plan-type";

export enum ActionTypes {
  SET_CURRENT = "set_current_plan",
  SET_REPLACEMENT = "set_replacement_plan",
  VERSION_CURRENT = "set_current_plan_version",
  VERSION_REPLACEMENT = "set_replacement_plan_version",
  SET_SUBSTITUTION_CALLBACK = "set_substitution_callback",
  SET_NAME = "set_name",
  SET_RANGE = "set_range",
  INIT = "init",
}

export type State = {
  currentPlan: PlanType | null;
  replacementPlan: PlanType | null;
  currentPlanVersion: PlanVersionType | null;
  replacementPlanVersion: PlanVersionType | null;
  onSubstitutionChange: (() => void) | null;
  experimentName: string | null;
  dateRange: string | null;
};

export type Actions = {
  type: ActionTypes;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any;
};

export type ActionCreators = {
  setCurrentPlan: (data: PlanType | null) => void;
  setReplacementPlan: (data: PlanType | null) => void;
  setCurrentPlanVersion: (data: PlanVersionType | null) => void;
  setExperimentName: (data: string | null) => void;
  setDateRange: (data: string | null) => void;
  setReplacementPlanVersion: (data: PlanVersionType | null) => void;
  setOnSubstitutionChangeFn: <T>(data: T) => void;
  init: () => void;
};
