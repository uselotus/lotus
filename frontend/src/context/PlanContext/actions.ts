import { ActionTypes } from "./types";
import { PlanType } from "../../types/plan-type";

// Action creators
export function setCurrentPlan(data: PlanType) {
  return {
    type: ActionTypes.SET_CURRENT,
    payload: data,
  };
}

export function setReplacementPlan(data: PlanType) {
  return {
    type: ActionTypes.SET_REPLACEMENT,
    payload: data,
  };
}

export function setOnSubstitutionChangeFn<T>(data: T) {
  return {
    type: ActionTypes.SET_SUBSTITUTION_CALLBACK,
    payload: data,
  };
}

export function init() {
  return {
    type: ActionTypes.INIT,
  };
}
