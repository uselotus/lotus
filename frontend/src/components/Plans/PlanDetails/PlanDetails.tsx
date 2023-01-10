// @ts-ignore
import React, { FC, Fragment } from "react";
import "./PlanDetails.css";
import { PageLayout } from "../../base/PageLayout";
import { Button } from "antd";
import { useNavigate, useParams } from "react-router-dom";
import SwitchVersions from "./SwitchVersions";
import { useMutation, useQuery, useQueryClient } from "react-query";
import { Plan } from "../../../api/api";
import {
  CreatePlanExternalLinkType,
  InitialExternalLinks,
  PlanDetailType,
} from "../../../types/plan-type";
import { PlusOutlined } from "@ant-design/icons";
import LoadingSpinner from "../../LoadingSpinner";
import { toast } from "react-toastify";

type PlanDetailParams = {
  planId: string;
};

const PlanDetails: FC = () => {
  const navigate = useNavigate();

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
  } = useQuery<PlanDetailType>(
    ["plan_detail", planId],
    () =>
      Plan.getPlan(planId as string).then((res) => {
        return res;
      }),
    { refetchOnMount: "always" }
  );

  const navigateCreateCustomPlan = () => {
    navigate("/create-custom/" + planId);
  };

  return (
    <Fragment>
      {isLoading && (
        <div className="flex h-full">
          <div className="m-auto">
            <LoadingSpinner />
          </div>
        </div>
      )}
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
              plan.target_customer !== null ? (
                <div>
                  {" "}
                  plan.plan_name + ": " + (plan.target_customer?.name ??
                  plan.target_customer?.customer_id.substring(0, 8))
                  <span className="block mt-4 text-neutral-500 text-base">
                    {plan.display_version.description}
                  </span>
                </div>
              ) : (
                <div>
                  {plan.plan_name}
                  <span className="block mt-4 text-neutral-500 text-base">
                    {plan.display_version.description}
                  </span>
                </div>
              )
            }
            hasBackButton
            backButton={
              <div className="mt-10">
                <Button
                  onClick={() => navigate(-1)}
                  type="primary"
                  size="large"
                  className="ml-[10px]"
                  key="create-custom-plan"
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
            extra={
              plan.target_customer === null && [
                <Button
                  onClick={navigateCreateCustomPlan}
                  type="primary"
                  size="large"
                  key="create-custom-plan"
                  style={{ background: "#C3986B", borderColor: "#C3986B" }}
                >
                  <div className="flex items-center justify-between text-white">
                    <div>
                      <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
                      Create Custom Plan
                    </div>
                  </div>
                </Button>,
              ]
            }
          ></PageLayout>
          <div className="mx-10">
            {plan.versions.length > 0 && (
              <SwitchVersions
                versions={plan.versions}
                createPlanExternalLink={createPlanExternalLink}
                deletePlanExternalLink={deletePlanExternalLink}
                plan={plan}
                className="flex items-center mx-10 my-5"
              />
            )}
          </div>
          <div className="separator mt-4" />
        </div>
      )}
    </Fragment>
  );
};
export default PlanDetails;
