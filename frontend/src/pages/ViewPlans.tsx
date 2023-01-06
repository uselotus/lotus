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
  const [quarterlyPlans, setQuarterlyPlans] = useState<PlanType[]>([]);
  const [quarterlyCustom, setQuarterlyCustom] = useState<PlanType[]>([]);
  const [allPlans, setAllPlans] = useState<PlanType[]>([]);
  const [allCustom, setAllCustom] = useState<PlanType[]>([]);

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
    const quarterlystandard = data.filter(
      (plan) => plan.plan_duration === "quarterly" && !plan.parent_plan
    );
    const quarterlycustom = data.filter(
      (plan) => plan.plan_duration === "quarterly" && plan.parent_plan
    );
    const allcustom = data.filter((plan) => plan.parent_plan);
    const allplans = data.filter((plan) => !plan.parent_plan);

    setAllCustom(allcustom);
    setAllPlans(allplans);
    setYearlyPlans(yearlystandard);
    setMonthlyPlans(monthlystandard);
    setYearlyCustom(yearlycustom);
    setMonthlyCustom(monthlycustom);
    setQuarterlyPlans(quarterlystandard);
    setQuarterlyCustom(quarterlycustom);
  };
  const createTag = useMutation(
    ({ plan_id, tags }: { plan_id: string; tags: PlanType["tags"] }) =>
      Plan.updatePlan(plan_id, {
        tags,
      }),
    {
      onSuccess: (_, { plan_id }) => {
        queryClient.invalidateQueries("plan_list");
        queryClient.invalidateQueries(["plan_detail", plan_id]);
        queryClient.invalidateQueries("organization");
      },
    }
  );
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
      refetchOnMount: "always",
    }
  );

  useEffect(() => {
    if (data) {
      setPlans(data);
    }
  }, []);

  return (
    <PageLayout
      title="Plans"
      className="font-arimo text-[24px]"
      extra={[
        <Button
          onClick={navigateCreatePlan}
          type="primary"
          size="large"
          key="create-plan"
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
        >
          <div className="flex items-center  justify-between text-white">
            <div>Create Plan</div>
            <ArrowRightOutlined className="pl-2" />
          </div>
        </Button>,
      ]}
    >
      <Tabs className="font-arimo" defaultActiveKey="0" size="large">
        <Tabs.TabPane tab="All" key="0">
          <div className="grid gap-6  grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
            {allPlans?.map((item, key) => (
              <PlanCard
                createTagMutation={createTag.mutate}
                plan={item}
                key={key}
              />
            ))}

            <div>
              {allCustom?.length > 0 && <h2>Custom Plans</h2>}

              <div className="grid gap-6 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {allCustom?.map((item, key) => (
                  <PlanCard
                    createTagMutation={createTag.mutate}
                    plan={item}
                    key={key}
                  />
                ))}
              </div>
            </div>
          </div>
        </Tabs.TabPane>

        <Tabs.TabPane tab="Monthly" key="1">
          <div className="grid gap-6 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
            {monthlyPlans?.map((item, key) => (
              <PlanCard
                createTagMutation={createTag.mutate}
                plan={item}
                key={key}
              />
            ))}

            <div>
              {monthlyCustom?.length > 0 && <h2>Custom Plans</h2>}

              <div className="grid gap-6 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {monthlyCustom?.map((item, key) => (
                  <PlanCard
                    createTagMutation={createTag.mutate}
                    plan={item}
                    key={key}
                  />
                ))}
              </div>
            </div>
          </div>
        </Tabs.TabPane>
        <Tabs.TabPane tab="Quarterly" key="2">
          <div className="grid gap-6  grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
            {quarterlyPlans?.map((item, key) => (
              <PlanCard
                createTagMutation={createTag.mutate}
                plan={item}
                key={key}
              />
            ))}

            <div>
              {quarterlyCustom?.length > 0 && <h2>Custom Plans</h2>}
              <div className="grid gap-6 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {quarterlyCustom?.map((item, key) => (
                  <PlanCard
                    createTagMutation={createTag.mutate}
                    plan={item}
                    key={key}
                  />
                ))}
              </div>
            </div>
          </div>
        </Tabs.TabPane>
        <Tabs.TabPane tab="Yearly" key="3">
          <div className="grid gap-6 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
            {yearlyPlans?.map((item, key) => (
              <PlanCard
                createTagMutation={createTag.mutate}
                plan={item}
                key={key}
              />
            ))}

            <div>
              {yearlyCustom?.length > 0 && <h2>Custom Plans</h2>}
              <div className="grid gap-6 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {yearlyCustom?.map((item, key) => (
                  <PlanCard
                    createTagMutation={createTag.mutate}
                    plan={item}
                    key={key}
                  />
                ))}
              </div>
            </div>
          </div>
        </Tabs.TabPane>
      </Tabs>
    </PageLayout>
  );
};

export default ViewPlans;
