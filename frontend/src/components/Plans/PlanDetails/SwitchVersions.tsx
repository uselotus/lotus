// @ts-ignore

import React, { FC, Fragment, useEffect, useState } from "react";

import "./SwitchVersions.css";
import { PlusOutlined, MoreOutlined, DeleteOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { Dropdown, Menu, Button, Typography } from "antd";
import dayjs from "dayjs";
import { useMutation, useQueryClient } from "react-query";
import {
  PlanDetailType,
  PlanType,
  PlanVersionType,
} from "../../../types/plan-type";
import PlanComponents, { PlanInfo, PlanSummary } from "./PlanComponent";
import PlanFeatures from "./PlanFeatures";
import StateTabs from "./StateTabs";
// @ts-ignore
import { Plan } from "../../../api/api";

interface SwitchVersionProps {
  versions: PlanVersionType[];
  plan: PlanDetailType;
  refetch: VoidFunction;
  className: string;
  createPlanExternalLink: (link: string) => void;
  deletePlanExternalLink: (link: string) => void;
}

// function that takes in a string and returns a string based on the cases of the string equals percentage, flat, or override
function getPriceAdjustmentEnding(
  type: string | undefined,
  amount: number | undefined,
  code: string
) {
  switch (type) {
    case "percentage":
      return `${amount  }%`;
    case "fixed":
      return `${code} ${amount}`;
    case "price_override":
      return `${code} ${amount}`;
    default:
      return "No discount added";
  }
}

function capitalize(word: string) {
  return word[0].toUpperCase() + word.slice(1).toLowerCase();
}

const SwitchVersions: FC<SwitchVersionProps> = ({
  versions,
  plan,
  refetch,
  createPlanExternalLink,
  deletePlanExternalLink,
  className,
}) => {
  const activePlanVersion = versions.find((x) => x.status === "active");

  const [selectedVersion, setSelectedVersion] = useState<
    PlanVersionType | undefined
  >(activePlanVersion);
  const [capitalizedState, setCapitalizedState] = useState<string>("");
  const queryClient = useQueryClient();

  const isSelectedVersion = (other_id: string) =>
    selectedVersion?.version_id === other_id;
  const createTag = useMutation(
    ({ plan_id, tags }: { plan_id: string; tags: PlanType["tags"] }) =>
      Plan.updatePlan(plan_id, {
        tags,
      }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("plan_list");
        queryClient.invalidateQueries(["plan_detail", plan.plan_id]);
      },
    }
  );
  const updateBillingFrequency = useMutation(
    (plan_duration: "monthly" | "quarterly" | "yearly") =>
      Plan.updatePlan(plan.plan_id, {
        plan_duration,
      }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("plan_list");
        queryClient.invalidateQueries(["plan_detail", plan.plan_id]);
        queryClient.invalidateQueries("organization");
      },
    }
  );

  // useEffect(() => {
  //   setSelectedVersion(versions.find((x) => x.status === "active")!);
  // }, [versions]);
  useEffect(() => {
    setSelectedVersion(plan.versions.find((x) => x.status === "active")!);
  }, [plan]);
  useEffect(() => {
    setCapitalizedState(capitalize(selectedVersion!.status));
  }, [selectedVersion?.status]);
  if (!activePlanVersion) {
    return <div>No Active Plan</div>;
  }

  return (
    <div>
      <div className={className}>
        {versions.map((version) => (
          <div
            onClick={(e) => {
              console.log(e.target);
              refetch();
              setSelectedVersion(version);
            }}
            className={[
              "flex items-center justify-center p-4 cursor-pointer mx-1",
              isSelectedVersion(version.version_id)
                ? "bg-[#c3986b] text-white opacity-100 ml-2 mr-2"
                : "bg-[#EAEAEB] text-black ml-2 mr-2",
              version.status === "active" &&
                "border-2 border-[#c3986b] border-opacity-100 ml-2 mr-2",
            ].join(" ")}
          >
            v{version.version}
          </div>
        ))}
        <Link
          type="text"
          to={`/create-version/${  selectedVersion?.plan_id}`}
          className="mx-4"
        >
          <div className="flex items-center justify-center px-2 py-2 rounded-[20px] hover:bg-[#EAEAEB]">
            <div className="addVersionButton">
              <PlusOutlined />
            </div>
            <div className=" text-[#1d1d1f]">Add new version</div>
          </div>
        </Link>
      </div>
      <div className="bg-white mb-6 flex flex-col py-4 px-10 rounded-lg space-y-12">
        <div className="grid gap-12 grid-cols-1  md:grid-cols-3">
          <div className="col-span-1">
            <PlanSummary
              plan={plan}
              createPlanExternalLink={createPlanExternalLink}
              createTagMutation={createTag.mutate}
              deletePlanExternalLink={deletePlanExternalLink}
            />
          </div>
          <div className="col-span-2">
            <PlanInfo plan={plan} version={selectedVersion!} />
          </div>
        </div>

        <div>
          <PlanComponents
            refetch={refetch}
            updateBillingFrequencyMutation={updateBillingFrequency.mutate}
            plan={plan}
            components={selectedVersion?.components}
            alerts={selectedVersion?.alerts}
            plan_version_id={selectedVersion!.version_id}
          />
        </div>
        <div>
          <PlanFeatures features={selectedVersion?.features} />
        </div>

        <div className=" mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card">
          <Typography.Title className="!text-[18px]">
            Price Adjustments:{" "}
            {getPriceAdjustmentEnding(
              selectedVersion?.price_adjustment?.price_adjustment_type,
              selectedVersion?.price_adjustment?.price_adjustment_amount,
              selectedVersion!.currency.symbol
            )}
          </Typography.Title>
        </div>

        {/* <div className="px-4 flex justify-start align-middle ">
          <div className="pb-5 font-main font-bold">Transition To:</div>
          <div className="mb-5 px-4 font-main font-bold self-center">
            {selectedVersion.transition_to || "------"}
          </div>
        </div> */}

        {/* <div className="px-4 py-4 flex items-center justify-between">
          <div className="pb-5 pt-3 font-main font-bold text-[20px]">
            Localisation:
          </div>
          <div>
            <Button size="large" key="use lotus recommended">
              Use Lotus Recommended
            </Button>
          </div>
        </div> */}
      </div>
    </div>
  );
};
export default SwitchVersions;
