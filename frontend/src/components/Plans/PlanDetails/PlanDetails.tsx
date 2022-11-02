// @ts-ignore
import React, { FC, Fragment } from "react";
import "./PlanDetails.css";
import { PageLayout } from "../../base/PageLayout";
import { Button, Col, Dropdown, Menu, Row, Switch, Tabs } from "antd";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import SwitchVersions from "./SwitchVersions";
import { useQuery } from "react-query";
import { Plan } from "../../../api/api";
import { PlanDetailType } from "../../../types/plan-type";
import LoadingSpinner from "../../LoadingSpinner";
import LinkExternalIds from "../LinkExternalIds";

type PlanDetailParams = {
  planId: string;
};

const PlanDetails: FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { planId } = useParams<PlanDetailParams>();
  //@todo Have to add the code to load details using the Plan Id

  const {
    data: plan,
    isLoading,
    isError,
  } = useQuery<PlanDetailType>(
    ["plan_detail", planId],
    () =>
      Plan.getPlan(planId).then((res) => {
        return res;
      }),
    { refetchOnMount: "always" }
  );

  const navigateCreateCustomPlan = () => {
    navigate("/create-custom/" + planId);
  };

  return (
    <Fragment>
      {isLoading && <LoadingSpinner />}
      {isError && (
        <div className="flex flex-col items-center justify-center h-full">
          <h2 className="mb-5">Could Not Load Plan</h2>
          <Button type="primary" onClick={() => navigate(-1)}>
            Go Back
          </Button>
        </div>
      )}
      {plan && (
        <div>
          <PageLayout
            title={
              plan.target_customer !== null
                ? plan.plan_name + ": " + plan.target_customer?.name
                : plan.plan_name
            }
            backIcon
            extra={
              plan.target_customer === null && [
                <Button
                  onClick={navigateCreateCustomPlan}
                  type="primary"
                  size="large"
                  key="create-custom-plan"
                >
                  <div className="flex items-center justify-between text-white">
                    <div>Create Custom Plan</div>
                  </div>
                </Button>,
              ]
            }
          ></PageLayout>
          <div className="mx-10">
            <div className="planDetails">
              <div className="pr-1 planDetailsLabel">Plan Id:</div>
              <div className="planDetailsValue"> {plan.plan_id}</div>
            </div>
            <div className="planDetails">
              <div className="pr-1 planDetailsLabel">Plan Duration:</div>
              <div className="planDetailsValue"> {plan.plan_duration}</div>
            </div>
              <div className="planDetails">
                  <div className="pr-1 planDetailsLabel">Linked External Ids:</div>
                  <div className="pl-2 mb-2">
                      <LinkExternalIds externalIds={[]}/>
                  </div>
              </div>
          </div>
          <div className="separator mt-4" />

          {plan.versions.length > 0 && (
            <SwitchVersions
              versions={plan.versions}
              className="flex items-center mx-10 my-5"
            />
          )}
        </div>
      )}
    </Fragment>
  );
};
export default PlanDetails;
