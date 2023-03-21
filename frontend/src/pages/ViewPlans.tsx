/* eslint-disable camelcase */
/* eslint-disable no-case-declarations */
/* eslint-disable no-plusplus */
/* eslint-disable no-shadow */
/* eslint-disable react/function-component-definition */
import React, { FC, useCallback, useEffect, useState } from "react";
import { Button, Tabs } from "antd";
// eslint-disable-next-line import/no-extraneous-dependencies
import { PlusOutlined } from "@ant-design/icons";
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
import { components } from "../gen-types";

// export interface Plan extends PlanType {
//   from: boolean;
// }
type Plan = components["schemas"]["Plan"] & { from: boolean };
const ViewPlans: FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [yearlyPlans, setYearlyPlans] = useState<
    components["schemas"]["Plan"][]
  >([]);
  const [yearlyCustom, setYearlyCustom] = useState<
    components["schemas"]["Plan"][]
  >([]);
  const [monthlyCustom, setMonthlyCustom] = useState<
    components["schemas"]["Plan"][]
  >([]);
  const [monthlyPlans, setMonthlyPlans] = useState<
    components["schemas"]["Plan"][]
  >([]);
  const [quarterlyPlans, setQuarterlyPlans] = useState<
    components["schemas"]["Plan"][]
  >([]);
  const [quarterlyCustom, setQuarterlyCustom] = useState<
    components["schemas"]["Plan"][]
  >([]);
  const [allPlans, setAllPlans] = useState<components["schemas"]["Plan"][]>([]);
  const [allCustom, setAllCustom] = useState<components["schemas"]["Plan"][]>(
    []
  );

  const [activeKey, setActiveKey] = useState("0");
  const [focus, setFocus] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [tagSearchQuery, setTagSearchQuery] = useState<string[]>([]);
  const [plansWithTagsFilter, setPlansWithTagsFilter] = useState<Plan[]>([]);
  const [isDisplayed, setIsDisplayed] = useState(false);

  const { plan_tags } = useGlobalStore((state) => state.org);

  const navigateCreatePlan = () => {
    navigate("/create-plan");
  };
  const changeTab = (activeKey: string) => {
    // setTagSearchQuery([]);
    // setSearchQuery("");
    setIsDisplayed(false);
    setActiveKey(activeKey);
  };
  const setPlans = useCallback(
    (
      data: components["schemas"]["Plan"][],
      tabPane?: "Monthly" | "Yearly" | "Quarterly" | "All"
    ) => {
      if (tabPane) {
        // go through all possible matches and set state
        switch (tabPane) {
          case "All":
            setAllPlans(data.filter((plan) => !plan.parent_plan));
            setAllCustom(data.filter((plan) => plan.parent_plan));
            return;
          case "Monthly":
            setMonthlyPlans(
              data.filter(
                (plan) => plan.plan_duration === "monthly" && !plan.parent_plan
              )
            );
            setMonthlyCustom(
              data.filter(
                (plan) => plan.plan_duration === "monthly" && plan.parent_plan
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
        const allplans = data.filter((plan) => !plan.parent_plan);
        const allcustom = data.filter((plan) => plan.parent_plan);

        setAllPlans(allplans);
        setAllCustom(allcustom);
        setMonthlyPlans(monthlystandard);
        setQuarterlyPlans(quarterlystandard);
        setYearlyPlans(yearlystandard);
        setYearlyCustom(yearlycustom);
        setMonthlyCustom(monthlycustom);
        setQuarterlyCustom(quarterlycustom);
      }
    },
    []
  );
  const { data }: UseQueryResult<components["schemas"]["Plan"][]> = useQuery<
    components["schemas"]["Plan"][]
  >(
    ["plan_list"],
    () =>
      Plan.getPlans({
        version_custom_type: "public_only",
        version_status: ["active"],
      }).then((res) => res),
    {
      onSuccess: (data) => {
        setPlans(data);
      },
      refetchOnMount: "always",
    }
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
      Plan.createTagsPlan(plan_id, {
        tags,
      }),
    {
      onSuccess: (newData, { plan_id }) => {
        if (data) {
          const oldData = [...data];
          const index = oldData.findIndex((plan) => plan.plan_id === plan_id);
          const changedElement = oldData.find(
            (plan) => plan.plan_id === plan_id
          );
          if (index && changedElement) {
            changedElement.tags = newData.tags as PlanType["tags"];
            oldData[index] = changedElement;
            setPlans(oldData);
          }
        }

        queryClient.invalidateQueries(["plan_detail", plan_id]);
        queryClient.invalidateQueries("organization");
      },
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
  }, [
    activeKey,
    searchQuery,
    allPlans,
    monthlyPlans,
    quarterlyPlans,
    yearlyPlans,
  ]);
  const getFilteredTagsAllPlans = useCallback(
    (tagName: string) => {
      switch (activeKey) {
        case "0":
          const r = allPlans
            .map((el, index) => ({ ...el, index }))
            .filter((plan) => plan.tags.length);
          let p2: Plan | undefined;
          for (let index = 0; index < r.length; index++) {
            const element = r[index];
            const idx = element.index;
            for (let j = 0; j < element.tags.length; j++) {
              const tags = element.tags as any[];
              if (tags[j].tag_name.toLowerCase().includes(tagName)) {
                p2 = allPlans[idx] as Plan;
              }
            }
          }
          if (p2) {
            p2.from = true;
          }

          return p2;

        case "1":
          const rs = monthlyPlans
            .map((el, index) => ({ ...el, index }))
            .filter((plan) => plan.tags.length);
          let p: Plan | undefined;
          for (let index = 0; index < rs.length; index++) {
            const element = rs[index];
            const idx = element.index;
            for (let j = 0; j < element.tags.length; j++) {
              const tags = element.tags as any[];
              if (tags[j].tag_name.toLowerCase().includes(tagName)) {
                p = allPlans[idx] as Plan;
              }
            }
          }
          if (p) {
            p.from = true;
          }

          return p;
        case "2":
          const r3 = monthlyPlans
            .map((el, index) => ({ ...el, index }))
            .filter((plan) => plan.tags.length);
          let p3: Plan | undefined;
          for (let index = 0; index < r3.length; index++) {
            const element = r3[index];
            const idx = element.index;
            for (let j = 0; j < element.tags.length; j++) {
              const tags = element.tags as any[];
              if (tags[j].tag_name.toLowerCase().includes(tagName)) {
                p3 = allPlans[idx] as Plan;
              }
            }
          }
          if (p3) {
            p3.from = true;
          }

          return p3;
        default:
          const r4 = monthlyPlans
            .map((el, index) => ({ ...el, index }))
            .filter((plan) => plan.tags.length);
          let p4: Plan | undefined;
          for (let index = 0; index < r4.length; index++) {
            const element = r4[index];
            const idx = element.index;
            for (let j = 0; j < element.tags.length; j++) {
              const tags = element.tags as any[];
              if (tags[j].tag_name.toLowerCase().includes(tagName)) {
                p4 = allPlans[idx] as Plan;
              }
            }
          }
          if (p4) {
            p4.from = true;
          }

          return p4;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data, tagSearchQuery]
  );

  useEffect(() => {
    switch (activeKey) {
      case "0":
        if (!tagSearchQuery.length && allPlans) {
          const p = allPlans.map((el) => ({ ...el, from: false }));

          setPlansWithTagsFilter(p);
        } else if (!tagSearchQuery.length) {
          const p = allPlans.map((el) => ({ ...el, from: false }));
          setPlansWithTagsFilter(p);
        }
        break;
      case "1":
        if (!tagSearchQuery.length && monthlyPlans) {
          const p = monthlyPlans.map((el) => ({ ...el, from: false }));

          setPlansWithTagsFilter(p);
        } else if (!tagSearchQuery.length) {
          const p = monthlyPlans.map((el) => ({ ...el, from: false }));
          setPlansWithTagsFilter(p);
        }
        break;
      case "2":
        if (!tagSearchQuery.length && quarterlyPlans) {
          const p = quarterlyPlans.map((el) => ({ ...el, from: false }));

          setPlansWithTagsFilter(p);
          return;
        }
        if (!tagSearchQuery.length) {
          const p = quarterlyPlans.map((el) => ({ ...el, from: false }));
          setPlansWithTagsFilter(p);
        }
        break;
      default:
        if (!tagSearchQuery.length && yearlyPlans) {
          const p = yearlyPlans.map((el) => ({ ...el, from: false }));

          setPlansWithTagsFilter(p);
          return;
        }
        if (!tagSearchQuery.length) {
          const p = yearlyPlans.map((el) => ({ ...el, from: false }));
          setPlansWithTagsFilter(p);
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
  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsDisplayed(true);
    }, 10);
    return () => clearTimeout(timeout);
  }, [activeKey]);

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

                  if (result === undefined) {
                    return;
                  }
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
                  if (result === undefined) {
                    return;
                  }
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
                  ? getFilteredPlans().map((item) => (
                      <PlanCard
                        pane="All"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
                      />
                    ))
                  : plansWithTagsFilter?.map((item) => (
                      <PlanCard
                        pane="All"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
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
              {isDisplayed ? (
                <>
                  {allCustom?.length > 0 && (
                    <h2 className="text-center text-bold mb-8">Custom Plans</h2>
                  )}

                  <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4 mt-4">
                    {allCustom?.map((item) => (
                      <PlanCard
                        pane="All"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
                      />
                    ))}
                  </div>
                </>
              ) : null}
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
                  if (result === undefined) {
                    return;
                  }
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
                  if (result === undefined) {
                    return;
                  }
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
                  ? getFilteredPlans()?.map((item) => (
                      <PlanCard
                        pane="Monthly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
                      />
                    ))
                  : plansWithTagsFilter.map((item) => (
                      <PlanCard
                        pane="Monthly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
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
              {isDisplayed ? (
                <>
                  {monthlyCustom?.length > 0 && (
                    <h2 className="text-center mb-8">Custom Plans</h2>
                  )}

                  <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                    {monthlyCustom?.map((item) => (
                      <PlanCard
                        pane="Monthly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
                      />
                    ))}
                  </div>
                </>
              ) : null}
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
                if (result === undefined) {
                  return;
                }
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
                if (result === undefined) {
                  return;
                }
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
                  ? getFilteredPlans()?.map((item) => (
                      <PlanCard
                        pane="Quarterly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
                      />
                    ))
                  : plansWithTagsFilter.map((item) => (
                      <PlanCard
                        pane="Quarterly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
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
              {isDisplayed ? (
                <>
                  {quarterlyCustom?.length > 0 && (
                    <h2 className="text-center mb-8">Custom Plans</h2>
                  )}
                  <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                    {quarterlyCustom?.map((item) => (
                      <PlanCard
                        pane="Quarterly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
                      />
                    ))}
                  </div>
                </>
              ) : null}
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
                if (result === undefined) {
                  return;
                }
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
                if (result === undefined) {
                  return;
                }
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
                  ? getFilteredPlans()?.map((item) => (
                      <PlanCard
                        pane="Yearly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
                      />
                    ))
                  : plansWithTagsFilter.map((item) => (
                      <PlanCard
                        pane="Yearly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
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
              {isDisplayed ? (
                <>
                  {yearlyCustom?.length > 0 && (
                    <h2 className="text-center mb-8">Custom Plans</h2>
                  )}
                  <div className="grid gap-20 grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
                    {yearlyCustom?.map((item) => (
                      <PlanCard
                        pane="Yearly"
                        createTagMutation={createTag.mutate}
                        plan={item}
                        key={item.plan_id}
                      />
                    ))}
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </Tabs.TabPane>
      </Tabs>
    </PageLayout>
  );
};

export default ViewPlans;
