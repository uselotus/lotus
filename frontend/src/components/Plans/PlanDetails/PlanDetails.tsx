/* eslint-disable @typescript-eslint/no-non-null-assertion */
/* eslint-disable no-use-before-define */
/* eslint-disable no-shadow */
/* eslint-disable camelcase */
// @ts-ignore
import React, { FC, Fragment, useRef, useState } from "react";
import "./PlanDetails.css";
import { Button, Tabs, Select } from "antd";
import { useNavigate, useParams } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
  UseQueryResult,
} from "react-query";
import { PlusOutlined } from "@ant-design/icons";
import { toast } from "react-toastify";
import { PageLayout } from "../../base/PageLayout";
import SwitchVersions from "./SwitchVersions";
import { Plan } from "../../../api/api";
import {
  CreatePlanExternalLinkType,
  InitialExternalLinks,
  PlanDetailType,
  PlanType,
} from "../../../types/plan-type";
import LoadingSpinner from "../../LoadingSpinner";
import { components } from "../../../gen-types";
import CustomPlanDetails from "./CustomPlanDetails";

type PlanDetailParams = {
  planId: string;
};

const PlanDetails: FC = () => {
  const navigate = useNavigate();
  const [customPlans, setCustomPlans] =
    useState<components["schemas"]["PlanDetail"]["versions"]>();
  const [selectedCustomPlan, setSelectedCustomPlan] =
    React.useState<components["schemas"]["PlanDetail"]["versions"][0]>();
  const selectRef = useRef<HTMLSelectElement | null>(null!);
  const dropdownSelectRef = useRef<HTMLSelectElement | null>(null!);
  const [activeKey, setActiveKey] = useState("0");
  const { planId } = useParams<PlanDetailParams>();
  const queryClient = useQueryClient();

  const createExternalLinkMutation = useMutation(
    (post: CreatePlanExternalLinkType) => Plan.createExternalLinks(post),
    {
      onMutate: optimisticMutateCreateHandler,
      onSuccess: () => {
        toast.success("Successfully created Plan external links", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: (_, __, context) => {
        // roll back since it failed
        queryClient.setQueryData(
          ["plan_detail", planId],
          context?.previousPlan
        );
        toast.error("Failed to create Plan external links", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onSettled: () => {
        queryClient.invalidateQueries(["plan_detail", planId]);
      },
    }
  );

  const deleteExternalLinkMutation = useMutation(
    (post: InitialExternalLinks) => Plan.deleteExternalLinks(post),
    {
      onMutate: optimisticMutateDeleteHandler,
      onSuccess: () => {
        toast.success("Successfully deleted Plan external links", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: (_, __, context) => {
        // roll back since it failed
        queryClient.setQueryData(
          ["plan_detail", planId],
          context?.previousPlan
        );
        toast.error("Failed to delete Plan external links", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onSettled: () => {
        queryClient.invalidateQueries(["plan_detail", planId]);
      },
    }
  );
  async function optimisticMutateCreateHandler(newExternalLink) {
    // Cancel any outgoing refetches
    // (so they don't overwrite our optimistic update)
    await queryClient.cancelQueries({ queryKey: ["plan_detail", planId] });

    // Snapshot the previous value
    const previousPlan = queryClient.getQueryData(["plan_detail", planId]);

    // immutably remove value we don't need from the external link
    const external_link: Partial<CreatePlanExternalLinkType> = {
      ...newExternalLink,
    };

    delete external_link.plan_id;

    // Optimistically update to the new value
    queryClient.setQueryData(["plan_detail", planId], (old) => {
      const typed_old = old as PlanDetailType;
      typed_old.external_links.push(external_link as InitialExternalLinks);
      return typed_old;
    });
    return { previousPlan };
  }
  async function optimisticMutateDeleteHandler(newExternalLink) {
    // Cancel any outgoing refetches
    // (so they don't overwrite our optimistic update)
    await queryClient.cancelQueries({ queryKey: ["plan_detail", planId] });

    // Snapshot the previous value
    const previousPlan = queryClient.getQueryData(["plan_detail", planId]);

    // Optimistically update to the new value
    queryClient.setQueryData(["plan_detail", planId], (old) => {
      const typed_old = old as PlanDetailType;
      const updated_data = typed_old.external_links.filter(
        (link) => link.external_plan_id !== newExternalLink.external_plan_id
      );
      typed_old.external_links = updated_data;
      return typed_old;
    });
    return { previousPlan };
  }
  const createPlanExternalLink = (link: string) => {
    if (plan!.external_links.find((links) => links.external_plan_id === link)) {
      toast.error(`Duplicate  external link for ${plan!.plan_name}`, {
        position: toast.POSITION.TOP_CENTER,
      });
      return;
    }
    const data: CreatePlanExternalLinkType = {
      plan_id: plan!.plan_id,
      source: "stripe",
      external_plan_id: link,
    };
    createExternalLinkMutation.mutate(data);
  };

  const deletePlanExternalLink = (link: string) => {
    const data: InitialExternalLinks = {
      source: "stripe",
      external_plan_id: link,
    };
    deleteExternalLinkMutation.mutate(data);
  };

  const {
    data: plan,
    isLoading,
    isError,
    refetch,
  } = useQuery<components["schemas"]["PlanDetail"]>(
    ["plan_detail", planId],
    () => Plan.getPlan(planId as string, "public_only").then((res) => res),
    { refetchOnMount: "always" }
  );
  const {
    data: customPlanData,
  }: UseQueryResult<components["schemas"]["PlanDetail"]> = useQuery<
    components["schemas"]["PlanDetail"]
  >(
    ["plan_list"],
    () => Plan.getPlan(planId as string, "custom_only").then((res) => res),

    {
      onSuccess: (plan) => {
        setCustomPlans(plan.versions);
        setSelectedCustomPlan(plan.versions[0]);
      },
    }
  );
  const changeTab = (activeKey: string) => {
    setActiveKey(activeKey);
  };

  const navigateCreateCustomPlan = () => {
    navigate(`/create-custom/${planId}`);
  };

  return (
    <>
      {isLoading && (
        <div className="flex h-full">
          <div className="m-auto">
            <LoadingSpinner />
          </div>
        </div>
      )}
      {isError && (
        <div className="flex flex-col items-center justify-center h-full">
          <h2 className="4">Could Not Load Plan</h2>
          <Button type="primary" onClick={() => navigate(-1)}>
            Go Back
          </Button>
        </div>
      )}
      {plan && (
        <PageLayout
          title={
            <div>
              {plan.plan_name}
              <span className="block mt-4  text-neutral-500 text-base">
                {plan.plan_description}
              </span>
            </div>
          }
          hasBackButton
          aboveTitle
          mx={false}
          backButton={
            <div>
              <Button
                onClick={() => navigate(-1)}
                type="primary"
                size="large"
                key="go-back"
                style={{
                  background: "#FAFAFA",
                  borderColor: "#FAFAFA",
                }}
              >
                <div className="flex items-center justify-between text-black">
                  <div>&larr; Go back</div>
                </div>
              </Button>
            </div>
          }
          backIcon
          extra={[
            <Button
              onClick={navigateCreateCustomPlan}
              type="primary"
              size="large"
              key="create-custom-plan"
              className="hover:!bg-primary-700"
              style={{ background: "#C3986B", borderColor: "#C3986B" }}
            >
              <div className="flex items-center justify-between text-white">
                <div>
                  <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
                  Create Custom Plan
                </div>
              </div>
            </Button>,
          ]}
        >
          <div>
            <Tabs
              onChange={changeTab}
              defaultActiveKey="0"
              activeKey={activeKey}
              size="large"
            >
              <Tabs.TabPane tab="Versions" key="0">
                {plan.versions.length > 0 && (
                  <SwitchVersions
                    refetch={refetch}
                    activeKey={activeKey}
                    versions={plan.versions}
                    createPlanExternalLink={createPlanExternalLink}
                    deletePlanExternalLink={deletePlanExternalLink}
                    plan={plan}
                    className="flex items-center my-5"
                  />
                )}
              </Tabs.TabPane>
              <Tabs.TabPane tab="Custom Plans" key="1">
                <div>
                  <div className="flex items-center gap-4">
                    <span>Filters</span>
                    <Select
                      className=""
                      onChange={(e) => {
                        const selectedType = customPlans?.find(
                          (el) => el.plan_name === e
                        );

                        setSelectedCustomPlan(selectedType);
                      }}
                      value={selectedCustomPlan?.plan_name}
                    >
                      {customPlans?.map((el, index) => (
                        <Select.Option value={el.plan_name} key={index}>
                          {el.plan_name}
                        </Select.Option>
                      ))}
                    </Select>
                  </div>
                  {selectedCustomPlan && (
                    <CustomPlanDetails
                      activeKey={activeKey}
                      refetch={refetch}
                      version={selectedCustomPlan}
                      createPlanExternalLink={createPlanExternalLink}
                      deletePlanExternalLink={deletePlanExternalLink}
                      plan={plan!}
                    />
                  )}
                </div>
              </Tabs.TabPane>
            </Tabs>
          </div>
        </PageLayout>
      )}
    </>
  );
};
export default PlanDetails;
