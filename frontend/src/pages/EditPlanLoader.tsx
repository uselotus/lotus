// create react FC component called EditPlanLoader
import React, { Fragment, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "react-query";
import { Button } from "antd";
import { Plan } from "../api/api";
import { PlanDetailType } from "../types/plan-type";
import LoadingSpinner from "../components/LoadingSpinner";
import { usePlanState } from "../context/PlanContext";
import EditPlan from "./EditPlan";

type PlanDetailParams = {
  planId: string;
};

interface EditPlanLoaderProps {
  type: "backtest" | "version" | "custom";
}

function EditPlanLoader({ type }: EditPlanLoaderProps) {
  const navigate = useNavigate();
  const { planId } = useParams<PlanDetailParams>();
  const [versionIndex, setVersionIndex] = React.useState<number>();
  const { replacementPlanVersion } = usePlanState();

  const {
    data: plan,
    isLoading,
    isError,
  } = useQuery<PlanDetailType>(
    ["plan_detail", planId],
    () => Plan.getPlan(planId as string).then((res) => res),

    {}
  );

  useEffect(() => {
    if (plan !== undefined) {
      if (type === "backtest") {
        setVersionIndex(
          plan.versions.findIndex(
            (v) => v.version_id === replacementPlanVersion?.version_id
          )
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
      {plan !== undefined && versionIndex !== undefined && (
        <EditPlan type={type} plan={plan} versionIndex={versionIndex} />
      )}
    </>
  );
}
export default EditPlanLoader;
