import client from "@/lib/client";
import { useQuery } from "react-query";
import { Plan } from "../api/api";

type Response = {
  token: string;
};

export const getPlan = async (planId) => {
  const data = await Plan.getPlan(planId);
  console.log("data", data);
  return data?.data;
};

export default function usePlan() {
  return useQuery<Response, Error>("user", getPlan);
}
