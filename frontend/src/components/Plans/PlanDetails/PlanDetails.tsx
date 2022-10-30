// @ts-ignore
import React, { FC, Fragment } from "react";
import "./PlanDetails.css";
import { PageLayout } from "../../base/PageLayout";
import { Button, Col, Dropdown, Menu, Row, Switch, Tabs } from "antd";
import { MoreOutlined } from "@ant-design/icons";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import SwitchVersions from "../../SwitchVersions/SwitchVersions";
import PlanComponents from "./PlanComponent";
import PlanFeatures from "./PlanFeatures";
import StateTabs from "./StateTabs";
import { useQuery } from "react-query";
import { Plan } from "../../../api/api";
import { PlanDetailType } from "../../../types/plan-type";
import LoadingSpinner from "../../LoadingSpinner";

const PlanDetails: FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { planId } = useParams();
  //@todo Have to add the code to load details using the Plan Id

  const {
    data: plan,
    isLoading,
    isError,
  } = useQuery<PlanDetailType>(["plan_detail", planId], () =>
    Plan.getPlan(planId).then((res) => {
      return res;
    })
  );

  const navigateCreateCustomPlan = () => {
    navigate("/create-custom", { state: { plan: plan } });
  };

  const versions = [
    {
      version_name: "Version 4",
    },
    {
      version_name: "Version 3",
    },
    {
      version_name: "Version 2",
    },
    {
      version_name: "Version 1",
    },
  ];

  const menu = (
    <Menu>
      <Menu.Item key="1">Action 1</Menu.Item>
    </Menu>
  );

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
            title={plan?.plan_name}
            backIcon
            extra={[
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
            ]}
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
          </div>
          <div className="separator mt-4" />

          <SwitchVersions
            versions={versions}
            className="flex items-center mx-10 my-5"
          />

          <div className="bg-white mb-5 mx-10 py-4 px-10 rounded-lg">
            <div className="p-2 flex justify-between">
              <div className="text-2xl font-main px-4 flex items-center">
                <span className="pr-6">Plan Information</span>
                <StateTabs
                  activeTab={"Inactive"}
                  tabs={["Inactive", "Grandfathered", "Active"]}
                />
              </div>

              <div className="right-3" onClick={(e) => e.stopPropagation()}>
                <Dropdown overlay={menu} trigger={["click"]}>
                  <Button
                    type="text"
                    size="small"
                    onClick={(e) => e.preventDefault()}
                  >
                    <MoreOutlined />
                  </Button>
                </Dropdown>
              </div>
            </div>
            <div className="separator" />
            <div className="px-4 py-2">
              <div className="planDetails">
                <div className="planDetailsLabel"> {plan.description}</div>
              </div>
            </div>

            <div className="flex items-center px-4 py-2">
              <div className="w-2/5">
                <div className="flex items-baseline py-2">
                  <div className="planCost">$10</div>
                  <div className="pl-2 infoLabel">Recuring price</div>
                </div>
                <div className="py-2">
                  <div className="flex activeSubscriptions">
                    <div className="pr-1">
                      Total Active Subscriptions: {plan.active_subscriptions}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex flex-col items-start w-30">
                <div className="flex items-center planInfo py-2">
                  <div className="pr-2 infoLabel">Date Created:</div>
                  <div className="infoValue"> {plan.created}</div>
                </div>
                <div className="flex items-center planInfo py-2 mt-2">
                  <div className="pr-2 infoLabel">Plan on next cycle:</div>
                  <div className="infoValue"> self</div>
                </div>
              </div>

              <div className="flex flex-col items-start w-30">
                <div className="flex items-center planInfo py-2">
                  <div className="pr-2 infoLabel">Recurring Billing Type:</div>
                  <div className="infoValue"> Pay In Advance</div>
                </div>
                <div className="flex items-center planInfo py-2 mt-2">
                  <div className="pr-2 infoLabel">
                    Components Billing Frequency:
                  </div>
                  <div className="infoValue"> monthly</div>
                </div>
              </div>
            </div>

            <div className="px-4 py-2">
              <PlanComponents />
            </div>
            <div className="px-4 py-2">
              <PlanFeatures />
            </div>

            <div className="separator pt-4" />

            <div className="px-4 py-4 flex items-center justify-between">
              <div className="planDetails planComponentMetricName">
                Localisation:
              </div>
              <div>
                <Button size="large" key="use lotus recommended">
                  Use Lotus Recommended
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Fragment>
  );
};
export default PlanDetails;
