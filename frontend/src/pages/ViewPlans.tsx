import React, { FC, useCallback, useEffect, useState } from "react";
import { Button, Tabs } from "antd";
import { Plan } from "../api/api";
import { ArrowRightOutlined, PlusOutlined } from "@ant-design/icons";
import { PlanType } from "../types/plan-type";
import { useNavigate } from "react-router-dom";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "react-query";
import { PageLayout } from "../components/base/PageLayout";
import PlanCard from "../components/Plans/PlanCard/PlanCard";
import LoadingSpinner from "../components/LoadingSpinner";

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

  const setPlans = useCallback(
    (
      data: PlanType[],
      tabPane?: "Monthly" | "Yearly" | "Quarterly" | "All"
    ) => {
      if (tabPane) {
        // go through all possible matches and set state
        switch (tabPane) {
          case "All":
            setAllCustom(data.filter((plan) => plan.parent_plan));
            setAllPlans(data.filter((plan) => !plan.parent_plan));
            return;
          case "Monthly":
            setMonthlyCustom(
              data.filter(
                (plan) => plan.plan_duration === "monthly" && plan.parent_plan
              )
            );
            setMonthlyPlans(
              data.filter(
                (plan) => plan.plan_duration === "monthly" && !plan.parent_plan
              )
            );
            return;
          case "Yearly":
            setYearlyPlans(
              data.filter(
                (plan) => plan.plan_duration === "yearly" && !plan.parent_plan
              )
            );
            setYearlyCustom(
              data.filter(
                (plan) => plan.plan_duration === "yearly" && plan.parent_plan
              )
            );
            return;
          default:
            setQuarterlyPlans(
              data.filter(
                (plan) =>
                  plan.plan_duration === "quarterly" && !plan.parent_plan
              )
            );
            setQuarterlyCustom(
              data.filter(
                (plan) => plan.plan_duration === "quarterly" && plan.parent_plan
              )
            );
            return;
        }
      } else {
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
      }
    },
    []
  );
  const createTag = useMutation(
    ({
      plan_id,
      tags,
    }: {
      plan_id: string;
      tags: PlanType["tags"];
      pane: "Monthly" | "Yearly" | "Quarterly" | "All";
    }) =>
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
  }, [data, setPlans]);

  return (
    <PageLayout
      title="Plans"
      className="text-[24px]"
      extra={[
        <Button
          onClick={navigateCreatePlan}
          type="primary"
          size="large"
          key="create-plan"
          className="hover:!bg-primary-700"
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
        >
          <div className="flex items-center  justify-between text-white">
            <div>
              <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
              Create Plan
            </div>
            <ArrowRightOutlined className="pl-2" />
          </div>
        </Button>,
      ]}
    >
      <Tabs defaultActiveKey="0" size="large">
        <Tabs.TabPane tab="All" key="0">
          <div className="flex flex-col">
            {data ? (
              <div className="grid gap-20  grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {allPlans?.map((item, key) => (
                  <PlanCard
                    pane="All"
                    createTagMutation={createTag.mutate}
                    plan={item}
                    key={key}
                  />
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center">
                <div className="mt-[40%]" />
                <LoadingSpinner />
              </div>
            )}
            <div className="mt-12">
              {allCustom?.length > 0 && (
                <h2 className="text-center text-bold mb-4">Custom Plans</h2>
              )}

              <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4 mt-4">
                {allCustom?.map((item, key) => (
                  <PlanCard
                    pane="All"
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
          <div className="flex flex-col">
            {data ? (
              <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {monthlyPlans?.map((item, key) => (
                  <PlanCard
                    pane="Monthly"
                    createTagMutation={createTag.mutate}
                    plan={item}
                    key={key}
                  />
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center">
                <div className="mt-[40%]" />
                <LoadingSpinner />
              </div>
            )}
            <div className="mt-12">
              {monthlyCustom?.length > 0 && (
                <h2 className="text-center">Custom Plans</h2>
              )}

              <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {monthlyCustom?.map((item, key) => (
                  <PlanCard
                    pane="Monthly"
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
          <div className="flex flex-col">
            {data ? (
              <div className="grid gap-20  grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {quarterlyPlans?.map((item, key) => (
                  <PlanCard
                    pane="Quarterly"
                    createTagMutation={createTag.mutate}
                    plan={item}
                    key={key}
                  />
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center">
                <div className="mt-[40%]" />
                <LoadingSpinner />
              </div>
            )}
            <div className="mt-12">
              {quarterlyCustom?.length > 0 && (
                <h2 className="text-center">Custom Plans</h2>
              )}
              <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {quarterlyCustom?.map((item, key) => (
                  <PlanCard
                    pane="Quarterly"
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
          <div className="flex flex-col">
            {data ? (
              <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {yearlyPlans?.map((item, key) => (
                  <PlanCard
                    pane="Yearly"
                    createTagMutation={createTag.mutate}
                    plan={item}
                    key={key}
                  />
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center">
                <div className="mt-[40%]" />
                <LoadingSpinner />
              </div>
            )}
            <div className="mt-12">
              {yearlyCustom?.length > 0 && (
                <h2 className="text-center">Custom Plans</h2>
              )}
              <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {yearlyCustom?.map((item, key) => (
                  <PlanCard
                    pane="Yearly"
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
