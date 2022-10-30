// @ts-ignore
import React, { FC, useEffect, useState } from "react";
import { Button, Row, Col, Tabs } from "antd";
import { Plan } from "../api/api";
import { ArrowRightOutlined } from "@ant-design/icons";
import { Component, PlanType } from "../types/plan-type";
import { useNavigate } from "react-router-dom";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "react-query";
import { PageLayout } from "../components/base/PageLayout";
import { FeatureType } from "../types/feature-type";
import PlanCard from "../components/Plans/PlanCard/PlanCard";

const ViewPlans: FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [yearlyPlans, setYearlyPlans] = useState<PlanType[]>([]);
  const [yearlyCustom, setYearlyCustom] = useState<PlanType[]>([]);
  const [monthlyCustom, setMonthlyCustom] = useState<PlanType[]>([]);
  const [monthlyPlans, setMonthlyPlans] = useState<PlanType[]>([]);

  const navigateCreatePlan = () => {
    navigate("/create-plan");
  };

  const setPlans = (data: PlanType[]) => {
    const yearlystandard = data.filter(
      (plan) => plan.plan_duration === "yearly" && !plan.parent_plan
    );
    const yearlycustom = data.filter(
      (plan) => plan.plan_duration === "yearly" && plan.parent_plan
    );
    const monthlystandard = data.filter(
      (plan) => plan.plan_duration === "monthly" && !plan.parent_plan
    );
    const monthlycustom = data.filter(
      (plan) => plan.plan_duration === "monthly" && plan.parent_plan
    );

    setYearlyPlans(yearlystandard);
    setMonthlyPlans(monthlystandard);
    setYearlyCustom(yearlycustom);
    setMonthlyCustom(monthlycustom);
  };

  const { data, isLoading, isError }: UseQueryResult<PlanType[]> = useQuery<
    PlanType[]
  >(
    ["plan_list"],
    () =>
      Plan.getPlans().then((res) => {
        return res;
      }),
    {
      onSuccess: (data) => {
        setPlans(data);
      },
    }
  );

  useEffect(() => {
    if (data) {
      setPlans(data);
    }
  }, []);

  const features: FeatureType[] = [
    {
      feature_name: "string",
      feature_description: "string",
    },
  ];

  const components: Component[] = [
    {
      free_metric_units: "string",
      cost_per_batch: "12",
      metric_units_per_batch: "12",
      max_metric_units: "12",
      id: 12,
      billable_metric: {
        event_name: "12",
        property_name: "12",
        aggregation_type: "12",
        metric_type: "12",
      },
    },
  ];

  const plans: PlanType[] = [
    {
      plan_name: "40K Words",
      plan_duration: "monthly",
      description: "plan 1 description",
      flat_rate: 20,
      currency: "string",
      plan_id: 1,
      pay_in_advance: true,
      time_created: "string",
      billing_plan_id: "51c957f5-d53a-4a71-ab04325744f17ec",
      active_subscriptions: 20,
      features: features,
      components: components,
    },
    {
      plan_name: "100K Words",
      plan_duration: "plan 1 interval",
      description: "plan 1 description",
      flat_rate: 20,
      currency: "string",
      plan_id: 2,
      pay_in_advance: true,
      time_created: "string",
      billing_plan_id: "51c957f5-d53a-4a71-ab04325744f17ec",
      active_subscriptions: 20,
      features: features,
      components: components,
    },
    {
      plan_name: "Enterprise",
      interval: "plan 1 interval",
      description: "plan 1 description",
      flat_rate: 20,
      currency: "string",
      plan_id: 3,
      pay_in_advance: true,
      time_created: "string",
      billing_plan_id: "51c957f5-d53a-4a71-ab04325744f17ec",
      active_subscriptions: 20,
      features: features,
      components: components,
    },
  ];

  // const deletePlan = (version_id: string) => {
  //   mutation.mutate(version_id);
  // };

  return (
    <div>
      <PageLayout
        title="Plans"
        extra={[
          <Button
            onClick={navigateCreatePlan}
            type="primary"
            size="large"
            key="create-plan"
          >
            <div className="flex items-center justify-between text-white">
              <div>Create new Plan</div>
              <ArrowRightOutlined className="pl-2" />
            </div>
          </Button>,
        ]}
      >
        <Tabs defaultActiveKey="1" size="large">
          <Tabs.TabPane tab="Monthly" key="1">
            <div className=" flex flex-col space-y-6 ">
              <Row gutter={[24, 32]}>
                {monthlyPlans?.map((item, key) => (
                  <Col span={8} key={key}>
                    <PlanCard plan={item} />
                  </Col>
                ))}
              </Row>
              {monthlyCustom?.length > 0 && <h2>Custom Plans</h2>}

              <Row gutter={[24, 32]}>
                {monthlyCustom?.map((item, key) => (
                  <Col span={8} key={key}>
                    <PlanCard plan={item} />
                  </Col>
                ))}
              </Row>
            </div>
          </Tabs.TabPane>
          <Tabs.TabPane tab="Yearly" key="2">
            <div className=" flex flex-col space-y-6 ">
              <Row gutter={[24, 32]}>
                {yearlyPlans?.map((item, key) => (
                  <Col span={8} key={key}>
                    <PlanCard plan={item} />
                  </Col>
                ))}
              </Row>
              {yearlyCustom?.length > 0 && <h2>Custom Plans</h2>}
              <Row gutter={[24, 32]}>
                {yearlyCustom?.map((item, key) => (
                  <Col span={8} key={key}>
                    <PlanCard plan={item} />
                  </Col>
                ))}
              </Row>
            </div>
          </Tabs.TabPane>
        </Tabs>
      </PageLayout>
    </div>
  );
};

export default ViewPlans;
