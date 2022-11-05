import { ActionTypes } from "./types";
import { PlanType, PlanVersionType } from "../../types/plan-type";

// Action creators
export function setCurrentPlan(data: PlanType | null) {
  return {
    type: ActionTypes.SET_CURRENT,
    payload: data,
  };
}

export function setCurrentPlanVersion(data: PlanVersionType | null) {
  return {
    type: ActionTypes.VERSION_CURRENT,
    payload: data,
  };
}

export function setReplacementPlanVersion(data: PlanVersionType | null) {
  return {
    type: ActionTypes.VERSION_REPLACEMENT,
    payload: data,
  };
}

export function setReplacementPlan(data: PlanType | null) {
  return {
    type: ActionTypes.SET_REPLACEMENT,
    payload: data,
  };
}

export function setExperimentName(data: string | null) {
  return {
    type: ActionTypes.SET_NAME,
    payload: data,
  };
}

export function setDateRange(data: string | null) {
  return {
    type: ActionTypes.SET_RANGE,
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
