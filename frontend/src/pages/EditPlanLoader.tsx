// create react FC component called EditPlanLoader
import React, { Fragment, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from '@tanstack/react-query';
import { Button } from "antd";
import { Plan } from "../api/api";
import { PlanDetailType } from "../types/plan-type";
import LoadingSpinner from "../components/LoadingSpinner";
import { usePlanState } from "../context/PlanContext";
import EditPlan from "./EditPlan";

type PlanDetailParams = {
  planId: string;
  versionId?: string;
};

interface EditPlanLoaderProps {
  type: "backtest" | "version" | "custom" | "currency";
}

function EditPlanLoader({ type }: EditPlanLoaderProps) {
  const navigate = useNavigate();
  const { planId, versionId } = useParams<PlanDetailParams>();
  const [versionIndex, setVersionIndex] = React.useState<number>();
  const { replacementPlanVersion } = usePlanState();

  const {
    data: plan,
    isLoading,
    isError,
  } = useQuery<PlanDetailType>(["plan_detail", planId], async () => {
    if (!planId) {
      return Promise.reject(new Error("No plan id provided"));
    }

    const res = Plan.getPlan(planId);
    return res;
  });

  useEffect(() => {
    if (plan !== undefined) {
      if (type === "backtest") {
        setVersionIndex(
          plan.versions.findIndex(
            (v) => v.version_id === replacementPlanVersion?.version_id
          )
        );
      } else if (type === "currency") {
        setVersionIndex(
          plan.versions.findIndex((x) => x.version_id === versionId)
        );
      } else {
        setVersionIndex(plan.versions.findIndex((x) => x.status === "active"));
      }
    }
  }, [plan, replacementPlanVersion?.version_id, type]);

  return (
    <>
      {isLoading && (
        <div className="flex justify-center">
          <LoadingSpinner />{" "}
        </div>
      )}
      {isError && (
        <div className="flex flex-col items-center justify-center h-full">
          <h2 className="mb-4">Could Not Load Plan</h2>
          <Button type="primary" onClick={() => navigate(-1)}>
            Go Back
          </Button>
        </div>
      )}

      {plan !== undefined && versionIndex !== undefined ? (
        <EditPlan type={type} plan={plan} versionIndex={versionIndex} />
      ) : null}
    </>
  );
}
export default EditPlanLoader;
