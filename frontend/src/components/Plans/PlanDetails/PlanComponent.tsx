// @ts-ignore
import React, { FC, useRef } from "react";
import "./PlanDetails.css";
import { Table, Typography, Tag } from "antd";
import { CheckCircleOutlined } from "@ant-design/icons";
import StateTabs from "./StateTabs";
import {
  Component,
  PlanDetailType,
  PlanType,
  PlanVersionType,
  Tier,
} from "../../../types/plan-type";
import { PricingUnit } from "../../../types/pricing-unit-type";
import createShortenedText from "../helpers/createShortenedText";
import DropdownComponent from "../../base/Dropdown/Dropdown";
import PlansTags from "../PlanTags";
import LinkExternalIds from "../LinkExternalIds";
import capitalize from "../helpers/capitalize";
import CopyText from "../../base/CopytoClipboard";
import dayjs from "dayjs";
import useVersionStore from "../../../stores/useVersionStore";
import Badge from "../../base/Badges/Badges";
interface PlanComponentsProps {
  components?: Component[];
}
export const tagList = [
  { color: "text-tags-lg", hex: "#065F46", text: "Documentation" },
  {
    color: "text-emerald",
    hex: "#A7F3D0",
    text: "API Calls",
  },
  {
    color: "text-indigo-600",
    hex: "#4F46E5",
    text: "Metrics",
  },
  {
    color: "text-orange-400",
    hex: "#FB923C",
    text: "Words",
  },
];

const renderCost = (record: Tier, pricing_unit: PricingUnit) => {
  switch (record.type) {
    case "per_unit":
      return (
        <span>
          {pricing_unit.symbol}
          {record.cost_per_batch} per {record.metric_units_per_batch} Unit
        </span>
      );

    case "flat":
      return (
        <span>
          {pricing_unit.symbol}
          {record.cost_per_batch}{" "}
        </span>
      );

    case "free":
      return <span>{"Free"}</span>;
  }
};
interface PlanSummaryProps {
  createPlanExternalLink: (link: string) => void;
  deletePlanExternalLink: (link: string) => void;
  plan: PlanDetailType;
  createTagMutation: (variables: string[]) => void;
}
export const PlanSummary = ({
  plan,
  createTagMutation,
  createPlanExternalLink,
  deletePlanExternalLink,
}: PlanSummaryProps) => {
  const inputRef = useRef<HTMLInputElement | null>(null!);
  return (
    <div className="min-h-[200px]  min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card  shadow-lg hover:shadow-neutral-400">
      <Typography.Title className="pt-4 whitespace-pre-wrap" level={3}>
        Summary
      </Typography.Title>

      <div>
        <div className=" w-full h-[1.5px] mt-2 bg-card-divider mb-2" />
        <div className="flex items-center text-card-text justify-between gap-2 mb-1">
          <div className=" font-normal whitespace-nowrap leading-4">
            Plan ID
          </div>
          <div className="flex gap-1">
            {" "}
            <div>{createShortenedText(plan.plan_id)}</div>
            <CopyText showIcon onlyIcon textToCopy={plan.plan_id} />
          </div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">
            Total Active Subscriptions
          </div>
          <div>{plan.active_subscriptions}</div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">
            Linked External IDs
          </div>
          <div>
            {" "}
            <LinkExternalIds
              createExternalLink={createPlanExternalLink}
              deleteExternalLink={deletePlanExternalLink}
              externalIds={plan.external_links.map((l) => l.external_plan_id)}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">Tags</div>
          <div>
            {" "}
            <DropdownComponent>
              <DropdownComponent.Trigger>
                <PlansTags tags={plan.tags} />
              </DropdownComponent.Trigger>
              <DropdownComponent.Container>
                {plan.tags &&
                  plan.tags.map((tag, index) => (
                    <DropdownComponent.MenuItem
                      onSelect={() => {
                        //should actually serve as a delete
                      }}
                    >
                      <span key={index} className="flex gap-2 justify-between">
                        <span className="text-black">{tag} </span>
                        <CheckCircleOutlined className="!text-gold" />
                      </span>
                    </DropdownComponent.MenuItem>
                  ))}
                <DropdownComponent.MenuItem
                  onSelect={() => {
                    const tags = [...plan.tags];
                    tags.push(inputRef.current!.value);
                    createTagMutation(tags);
                  }}
                >
                  <input
                    type="text"
                    className="text-black outline-none"
                    placeholder="Custom tag..."
                    ref={inputRef}
                  />
                </DropdownComponent.MenuItem>
              </DropdownComponent.Container>
            </DropdownComponent>
          </div>
        </div>
      </div>
    </div>
  );
};
interface PlanInfoProps {
  version: PlanVersionType;
  plan: PlanDetailType;
}
export const PlanInfo = ({ version, plan }: PlanInfoProps) => {
  const constructBillType = (str: string) => {
    if (str.includes("_")) {
      return str
        .split("_")
        .map((el) => capitalize(el))
        .join(" ");
    } else {
      return str;
    }
  };
  const schedule = (day: Number) => {
    if (day >= 1 && day <= 10) {
      return "Start of Month";
    } else if (day >= 11 && day <= 20) {
      return "Middle of Month";
    } else {
      return "End of Month";
    }
  };
  console.log(
    Number(dayjs(version.created_on).format("YYYY/MM/DD").split("/")[2])
  );
  console.log(dayjs(version?.created_on).day());
  return (
    <div className="min-h-[200px]  min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card  shadow-lg hover:shadow-neutral-400">
      <Typography.Title
        className="pt-4 whitespace-pre-wrap grid gap-4 items-center grid-cols-1 md:grid-cols-2"
        level={3}
      >
        <div>Plan Information</div>
        <div>
          <StateTabs
            activeTab={capitalize(version.status)}
            version_id={version.version_id}
            version={version.version}
            activeVersion={version.version}
            tabs={["Active", "Grandfathered", "Retiring", "Inactive"]}
          />
        </div>
      </Typography.Title>
      <div className=" w-full h-[1.5px] mt-2 bg-card-divider mb-2" />
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
        <div>
          <div className="flex items-center text-card-text justify-between gap-2 mb-1">
            <div className=" font-normal whitespace-nowrap leading-4">
              Recurring Price
            </div>
            <div className="flex gap-1">
              {" "}
              <div className="text-gold">{`${plan.display_version.currency.symbol}${plan.display_version.flat_rate}`}</div>
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Plan Duration
            </div>
            <div>{capitalize(plan.plan_duration)}</div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Created At
            </div>
            <div> {dayjs(version?.created_on).format("YYYY/MM/DD")}</div>
          </div>
        </div>

        <div>
          <div className="flex items-center text-card-text justify-between gap-2 mb-1">
            <div className=" font-normal whitespace-nowrap leading-4">
              Plan on next cycle
            </div>
            <div className="flex gap-1 ">
              {" "}
              <div>
                {version?.transition_to
                  ? capitalize(version.transition_to)
                  : "Self"}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Recurring Bill Type
            </div>
            <div>
              {
                <Badge>
                  <Badge.Content>
                    {constructBillType(
                      plan.display_version.flat_fee_billing_type
                    )}
                  </Badge.Content>
                </Badge>
              }
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal whitespace-nowrap leading-4">
              Schedule
            </div>
            <div>
              {" "}
              <span>
                {schedule(
                  Number(
                    dayjs(version.created_on).format("YYYY/MM/DD").split("/")[2]
                  )
                )}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
const PlanComponents: FC<PlanComponentsProps> = ({ components }) => {
  return (
    <div className="">
      <div className="pb-5 pt-3 font-main font-bold text-[20px]">
        Components:
      </div>
      {components && components.length > 0 ? (
        <div className="flex items-stretch justify-start flex-wrap">
          {components.map((component) => (
            <div className="pt-2 pb-4 bg-[#FAFAFA] mr-4 mb-2 px-8 border-2 border-solid border-[#EAEAEB]">
              <div className="planDetails planComponentMetricName text-[20px] text-[#1d1d1fd9]">
                <div> {component.billable_metric.metric_name}</div>
              </div>
              <div>
                <Table
                  dataSource={component.tiers}
                  pagination={false}
                  showHeader={false}
                  bordered={false}
                  rowClassName="bg-[#FAFAFA]"
                  className="bg-background noborderTable"
                  style={{ color: "blue" }}
                  size="middle"
                  columns={[
                    {
                      title: "Range",
                      dataIndex: "range_start",
                      key: "range_start",
                      align: "left",
                      width: "50%",
                      render: (value: any, record: any) => (
                        <span>
                          From {value} to{" "}
                          {record.range_end == null ? "∞" : record.range_end}
                        </span>
                      ),
                    },
                    {
                      title: "Cost",
                      align: "left",
                      dataIndex: "cost_per_batch",
                      key: "cost_per_batch",
                      render: (value: any, record: any) => (
                        <div>{renderCost(record, component.pricing_unit)}</div>
                      ),
                    },
                  ]}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-start flex-wrap">
          No components
        </div>
      )}
    </div>
  );
};
export default PlanComponents;
