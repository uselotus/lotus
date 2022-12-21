// @ts-ignore
import React, { FC, Fragment } from "react";
import "./PlanDetails.css";
import { PageLayout } from "../../base/PageLayout";
import { Button } from "antd";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import SwitchVersions from "./SwitchVersions";
import { useMutation, useQuery, useQueryClient } from "react-query";
import { Plan } from "../../../api/api";
import {
  CreatePlanExternalLinkType,
  InitialExternalLinks,
  PlanDetailType,
} from "../../../types/plan-type";
import LoadingSpinner from "../../LoadingSpinner";
import LinkExternalIds from "../LinkExternalIds";
import { toast } from "react-toastify";
import CopyText from "../../base/CopytoClipboard";

type PlanDetailParams = {
  planId: string;
};

const PlanDetails: FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { planId } = useParams<PlanDetailParams>();
  const queryClient = useQueryClient();

  const createExternalLinkMutation = useMutation(
    (post: CreatePlanExternalLinkType) => Plan.createExternalLinks(post),
    {
      onMutate: async (newExternalLink) => {
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
      },
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
    }
  );

  const deleteExternalLinkMutation = useMutation(
    (post: InitialExternalLinks) => Plan.deleteExternalLinks(post),
    {
      onSuccess: () => {
        toast.success("Successfully deleted Plan external links", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Failed to delete Plan external links", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

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
  console.log(plan);
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
              plan.target_customer !== null
                ? plan.plan_name +
                  ": " +
                  (plan.target_customer?.name ??
                    plan.target_customer?.customer_id.substring(0, 8))
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
              <div className="pr-1 planDetailsLabel">Plan ID:</div>
              <div className="planDetailsValue">
                {" "}
                <CopyText showIcon textToCopy={plan.plan_id} />
              </div>
            </div>
            <div className="planDetails">
              <div className="pr-1 planDetailsLabel">Plan Duration:</div>
              <div className="planDetailsValue"> {plan.plan_duration}</div>
            </div>
            <div className="planDetails">
              <div className="pr-1 planDetailsLabel">Linked External Ids:</div>
              <div className="pl-2 mb-2">
                <LinkExternalIds
                  createExternalLink={createPlanExternalLink}
                  deleteExternalLink={deletePlanExternalLink}
                  externalIds={plan.external_links.map(
                    (l) => l.external_plan_id
                  )}
                />
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
