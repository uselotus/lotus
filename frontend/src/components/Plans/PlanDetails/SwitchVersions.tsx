// @ts-ignore
import React, { FC, Fragment, useEffect, useState, version } from "react";
import shallow from "zustand/shallow";
import "./SwitchVersions.css";
import { PlusOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import {
  PlanDetailType,
  PlanType,
  PlanVersionType,
} from "../../../types/plan-type";
import PlanComponents, { PlanInfo, PlanSummary } from "./PlanComponent";
import PlanFeatures from "./PlanFeatures";
import StateTabs from "./StateTabs";
import { Dropdown, Menu, Button, Typography } from "antd";
import { MoreOutlined } from "@ant-design/icons";
// @ts-ignore
import dayjs from "dayjs";
import { DeleteOutlined } from "@ant-design/icons";
import { Plan } from "../../../api/api";
import { useMutation, useQueryClient } from "react-query";

interface SwitchVersionProps {
  versions: PlanVersionType[];
  plan: PlanDetailType;
  className: string;
  createPlanExternalLink: (link: string) => void;
  deletePlanExternalLink: (link: string) => void;
}

//function that takes in a string and returns a string based on the cases of the string equals percentage, flat, or override
function getPriceAdjustmentEnding(
  type: string | undefined,
  amount: number | undefined,
  code: string
) {
  switch (type) {
    case "percentage":
      return amount + "%";
    case "fixed":
      return `${code} ${amount}`;
    case "price_override":
      return `${code} ${amount}`;
    default:
      return "No adjustment added";
  }
}

function capitalize(word: string) {
  return word[0].toUpperCase() + word.slice(1).toLowerCase();
}

const SwitchVersions: FC<SwitchVersionProps> = ({
  versions,
  plan,
  createPlanExternalLink,
  deletePlanExternalLink,
  className,
}) => {
  const activePlanVersion = versions.find((x) => x.status === "active");
  if (!activePlanVersion) {
    return <div>No Active Plan</div>;
  }

  const [selectedVersion, setSelectedVersion] =
    useState<PlanVersionType>(activePlanVersion);
  const [capitalizedState, setCapitalizedState] = useState<string>("");
  const queryClient = useQueryClient();

  const isSelectedVersion = (other_id: string) =>
    selectedVersion.version_id === other_id;
  const createTag = useMutation(
    (tags: PlanType["tags"]) =>
      Plan.updatePlan(plan.plan_id, {
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
  const archivemutation = useMutation(
    (version_id: string) =>
      Plan.archivePlanVersion(version_id, { status: "archived" }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("plan_list");
      },
    }
  );

  useEffect(() => {
    setCapitalizedState(capitalize(selectedVersion.status));
  }, [selectedVersion.status]);

  const menu = (
    <Menu>
      <Menu.Item
        key="1"
        onClick={() => archivemutation.mutate(selectedVersion.version_id)}
        disabled={
          selectedVersion.status === "active" ||
          selectedVersion.status === "grandfathered"
        }
      >
        <div className="planMenuArchiveIcon">
          <div>
            <DeleteOutlined />
          </div>
          <div className="archiveLabel">Archive</div>
        </div>
      </Menu.Item>
    </Menu>
  );

  return (
    <div>
      <div className={className}>
        {versions.map((version) => (
          <div
            onClick={() => setSelectedVersion(version)}
            className={
              isSelectedVersion(version.version_id) &&
              version.status === "active"
                ? "flex items-center justify-center p-4 text-sm mx-1 bg-[#c3986b] text-white opacity-100 border-2 border-[#c3986b] border-opacity-100"
                : "flex items-center justify-center p-4 text-sm mx-1 bg-[#EAEAEB] text-black"
            }
          >
            v{version.version}
          </div>
        ))}
        <Link
          type="text"
          to={"/create-version/" + selectedVersion.plan_id}
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
      <div className="bg-white mb-5 flex flex-col py-4 px-10 rounded-lg">
        <div className="grid gap-6 grid-cols-1  md:grid-cols-3">
          <div className="col-span-1">
            <PlanSummary
              plan={plan}
              createPlanExternalLink={createPlanExternalLink}
              createTagMutation={createTag.mutate}
              deletePlanExternalLink={deletePlanExternalLink}
            />
          </div>
          <div className="col-span-2">
            <PlanInfo plan={plan} version={selectedVersion} />
          </div>
        </div>

        <div className="px-4 py-2">
          <PlanComponents
            updateBillingFrequencyMutation={updateBillingFrequency.mutate}
            plan={plan}
            components={selectedVersion.components}
          />
        </div>
        <div className="px-4 py-2">
          <PlanFeatures features={selectedVersion.features} />
        </div>

        <div className="separator pt-4" />

        <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card  shadow-lg ">
          <Typography.Title level={2}>Price Adjustments</Typography.Title>
          <div className="mb-5 mt-3 px-4 font-main self-center">
            <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
            <div className="text-card-grey">
              {getPriceAdjustmentEnding(
                selectedVersion.price_adjustment?.price_adjustment_type,
                selectedVersion.price_adjustment?.price_adjustment_amount,
                selectedVersion.currency.symbol
              )}
            </div>
          </div>
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
