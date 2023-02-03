import React, { FC, useCallback, useEffect, useState } from "react";
import { Button, Tabs } from "antd";
import { ArrowRightOutlined, PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "react-query";
import { PlanType } from "../types/plan-type";
import { Plan } from "../api/api";
import { PageLayout } from "../components/base/PageLayout";
import PlanCard from "../components/Plans/PlanCard/PlanCard";
import LoadingSpinner from "../components/LoadingSpinner";
import ViewPlansFilter from "./ViewPlansFilter";
import useGlobalStore from "../stores/useGlobalstore";
export interface Plan extends PlanType {
  from: boolean;
}
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

  const [activeKey, setActiveKey] = useState("0");
  const [focus, setFocus] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [tagSearchQuery, setTagSearchQuery] = useState<string[]>([]);
  const [plansWithTagsFilter, setPlansWithTagsFilter] = useState<Plan[]>([]);
  const { plan_tags } = useGlobalStore((state) => state.org);

  const navigateCreatePlan = () => {
    navigate("/create-plan");
  };
  const changeTab = (activeKey: string) => {
    setActiveKey(activeKey);
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
  const { data }: UseQueryResult<PlanType[]> = useQuery<PlanType[]>(
    ["plan_list"],
    () => Plan.getPlans().then((res) => res),
    {
      onSuccess: (data) => {
        setPlans(data);
      },
      refetchOnMount: "always",
    }
  );

  const getFilteredPlans = useCallback(() => {
    switch (activeKey) {
      case "0":
        if (!searchQuery && allPlans) {
          return allPlans;
        }
        return allPlans.filter(
          (plan) =>
            plan.plan_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
            plan.plan_name.toLowerCase().includes(searchQuery.toLowerCase())
        );

      case "1":
        if (!searchQuery) {
          return monthlyPlans;
        }
        return monthlyPlans.filter(
          (plan) =>
            plan.plan_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
            plan.plan_name.toLowerCase().includes(searchQuery.toLowerCase())
        );
      case "2":
        if (!searchQuery) {
          return quarterlyPlans;
        }
        return quarterlyPlans.filter(
          (plan) =>
            plan.plan_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
            plan.plan_name.toLowerCase().includes(searchQuery.toLowerCase())
        );
      default:
        if (!searchQuery) {
          return yearlyPlans;
        }
        return yearlyPlans.filter(
          (plan) =>
            plan.plan_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
            plan.plan_name.toLowerCase().includes(searchQuery.toLowerCase())
        );
    }
  }, [data, searchQuery, activeKey]);
  const getFilteredTagsAllPlans = useCallback(
    (tagName: string) => {
      const r = allPlans
        .map((el, index) => ({ ...el, index }))
        .filter((plan) => plan.tags.length);
      let p: Plan | undefined = undefined;
      for (let index = 0; index < r.length; index++) {
        const element = r[index];
        const idx = element.index;
        for (let j = 0; j < element.tags.length; j++) {
          if (element.tags[j].tag_name.toLowerCase().includes(tagName)) {
            p = allPlans[idx] as Plan;
          }
        }
      }
      p!.from = true;

      return p;
    },
    [
      allPlans,
      data,
      activeKey,
      monthlyPlans,
      quarterlyPlans,
      yearlyPlans,
      tagSearchQuery,
    ]
  );

  useEffect(() => {
    if (data) {
      setPlans(data);
    }
  }, [data, setPlans]);
  useEffect(() => {
    switch (activeKey) {
      case "0":
        if (!tagSearchQuery.length && allPlans) {
          const p = allPlans.map((el) => ({ ...el, from: false }));

          setPlansWithTagsFilter(p);
          return;
        } else if (!tagSearchQuery.length) {
          const p = allPlans.map((el) => ({ ...el, from: false }));
          setPlansWithTagsFilter(p);
          return;
        }
        break;
      case "1":
        if (!tagSearchQuery.length && monthlyPlans) {
          const p = monthlyPlans.map((el) => ({ ...el, from: false }));

          setPlansWithTagsFilter(p);
          return;
        } else if (!tagSearchQuery.length) {
          const p = monthlyPlans.map((el) => ({ ...el, from: false }));
          setPlansWithTagsFilter(p);
          return;
        }
        break;
      case "2":
        if (!tagSearchQuery.length && quarterlyPlans) {
          const p = quarterlyPlans.map((el) => ({ ...el, from: false }));

          setPlansWithTagsFilter(p);
          return;
        } else if (!tagSearchQuery.length) {
          const p = quarterlyPlans.map((el) => ({ ...el, from: false }));
          setPlansWithTagsFilter(p);
          return;
        }
        break;
      default:
        if (!tagSearchQuery.length && yearlyPlans) {
          const p = yearlyPlans.map((el) => ({ ...el, from: false }));

          setPlansWithTagsFilter(p);
          return;
        } else if (!tagSearchQuery.length) {
          const p = yearlyPlans.map((el) => ({ ...el, from: false }));
          setPlansWithTagsFilter(p);
          return;
        }
    }
  }, [
    tagSearchQuery,
    allPlans,
    monthlyPlans,
    quarterlyPlans,
    yearlyPlans,
    activeKey,
  ]);

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
      <Tabs
        defaultActiveKey="0"
        activeKey={activeKey}
        onChange={changeTab}
        size="large"
      >
        <Tabs.TabPane tab="All" key="0">
          <div className="flex flex-col">
            <ViewPlansFilter
              value={searchQuery}
              tags={plan_tags}
              onFocusHandler={(focus) => setFocus(focus)}
              onChangeHandler={(e) => setSearchQuery(e.target.value)}
              onSelectHandler={(tag, remove) => {
                if (remove) {
                  const filter = tagSearchQuery.filter(
                    (t) => t !== tag.tag_name.toLowerCase()
                  )[0];
                  if (!filter) {
                    setTagSearchQuery([]);
                    setPlansWithTagsFilter([]);
                    return;
                  }

                  const result = getFilteredTagsAllPlans(filter);

                  setPlansWithTagsFilter(
                    plansWithTagsFilter.filter(
                      (plan) => plan.plan_name === result?.plan_name
                    )
                  );
                  setTagSearchQuery((prev) =>
                    prev.filter((t) => t !== tag.tag_name.toLowerCase())
                  );
                } else {
                  const result = getFilteredTagsAllPlans(
                    tag.tag_name.toLowerCase()
                  );
                  setPlansWithTagsFilter((prev) =>
                    prev
                      .filter((prev) => prev.from === true)
                      .concat(result as Plan)
                  );
                  setTagSearchQuery((prev) =>
                    prev.concat(tag.tag_name.toLowerCase())
                  );
                }
              }}
            />
            {data ? (
              <div className="grid gap-20  grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {focus
                  ? getFilteredPlans().map((item, key) => (
                      <PlanCard
                        pane="All"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={key}
                      />
                    ))
                  : plansWithTagsFilter?.map((item, key) => (
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
                <h2 className="text-center text-bold mb-8">Custom Plans</h2>
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
            <ViewPlansFilter
              value={searchQuery}
              tags={plan_tags}
              onFocusHandler={(focus) => setFocus(focus)}
              onChangeHandler={(e) => setSearchQuery(e.target.value)}
              onSelectHandler={(tag, remove) => {
                if (remove) {
                  const filter = tagSearchQuery.filter(
                    (t) => t !== tag.tag_name.toLowerCase()
                  )[0];
                  if (!filter) {
                    setTagSearchQuery([]);
                    setPlansWithTagsFilter([]);
                    return;
                  }

                  const result = getFilteredTagsAllPlans(filter);

                  setPlansWithTagsFilter(
                    plansWithTagsFilter.filter(
                      (plan) => plan.plan_name === result?.plan_name
                    )
                  );
                  setTagSearchQuery((prev) =>
                    prev.filter((t) => t !== tag.tag_name.toLowerCase())
                  );
                } else {
                  const result = getFilteredTagsAllPlans(
                    tag.tag_name.toLowerCase()
                  );
                  setPlansWithTagsFilter((prev) =>
                    prev
                      .filter((prev) => prev.from === true)
                      .concat(result as Plan)
                  );
                  setTagSearchQuery((prev) =>
                    prev.concat(tag.tag_name.toLowerCase())
                  );
                }
              }}
            />
            {data ? (
              <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {focus
                  ? getFilteredPlans()?.map((item, key) => (
                      <PlanCard
                        pane="Monthly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={key}
                      />
                    ))
                  : plansWithTagsFilter.map((item, key) => (
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
                <h2 className="text-center mb-8">Custom Plans</h2>
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
          <ViewPlansFilter
            value={searchQuery}
            tags={plan_tags}
            onFocusHandler={(focus) => setFocus(focus)}
            onChangeHandler={(e) => setSearchQuery(e.target.value)}
            onSelectHandler={(tag, remove) => {
              if (remove) {
                const filter = tagSearchQuery.filter(
                  (t) => t !== tag.tag_name.toLowerCase()
                )[0];
                if (!filter) {
                  setTagSearchQuery([]);
                  setPlansWithTagsFilter([]);
                  return;
                }

                const result = getFilteredTagsAllPlans(filter);

                setPlansWithTagsFilter(
                  plansWithTagsFilter.filter(
                    (plan) => plan.plan_name === result?.plan_name
                  )
                );
                setTagSearchQuery((prev) =>
                  prev.filter((t) => t !== tag.tag_name.toLowerCase())
                );
              } else {
                const result = getFilteredTagsAllPlans(
                  tag.tag_name.toLowerCase()
                );
                setPlansWithTagsFilter((prev) =>
                  prev
                    .filter((prev) => prev.from === true)
                    .concat(result as Plan)
                );
                setTagSearchQuery((prev) =>
                  prev.concat(tag.tag_name.toLowerCase())
                );
              }
            }}
          />
          <div className="flex flex-col">
            {data ? (
              <div className="grid gap-20  grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {focus
                  ? getFilteredPlans()?.map((item, key) => (
                      <PlanCard
                        pane="Quarterly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={key}
                      />
                    ))
                  : plansWithTagsFilter.map((item, key) => (
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
                <h2 className="text-center mb-8">Custom Plans</h2>
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
          <ViewPlansFilter
            value={searchQuery}
            tags={plan_tags}
            onFocusHandler={(focus) => setFocus(focus)}
            onChangeHandler={(e) => setSearchQuery(e.target.value)}
            onSelectHandler={(tag, remove) => {
              if (remove) {
                const filter = tagSearchQuery.filter(
                  (t) => t !== tag.tag_name.toLowerCase()
                )[0];
                if (!filter) {
                  setTagSearchQuery([]);
                  setPlansWithTagsFilter([]);
                  return;
                }

                const result = getFilteredTagsAllPlans(filter);

                setPlansWithTagsFilter(
                  plansWithTagsFilter.filter(
                    (plan) => plan.plan_name === result?.plan_name
                  )
                );
                setTagSearchQuery((prev) =>
                  prev.filter((t) => t !== tag.tag_name.toLowerCase())
                );
              } else {
                const result = getFilteredTagsAllPlans(
                  tag.tag_name.toLowerCase()
                );
                setPlansWithTagsFilter((prev) =>
                  prev
                    .filter((prev) => prev.from === true)
                    .concat(result as Plan)
                );
                setTagSearchQuery((prev) =>
                  prev.concat(tag.tag_name.toLowerCase())
                );
              }
            }}
          />
          <div className="flex flex-col">
            {data ? (
              <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                {focus
                  ? getFilteredPlans()?.map((item, key) => (
                      <PlanCard
                        pane="Yearly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={key}
                      />
                    ))
                  : plansWithTagsFilter.map((item, key) => (
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
                <h2 className="text-center mb-8">Custom Plans</h2>
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
