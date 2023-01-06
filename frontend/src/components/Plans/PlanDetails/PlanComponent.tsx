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
import Select from "../../base/Select/Select";
import useMediaQuery from "../../../hooks/useWindowQuery";
import createTags from "../helpers/createTags";
import useGlobalStore from "../../../stores/useGlobalstore";
interface PlanComponentsProps {
  components?: Component[];
  plan: PlanType;
  updateBillingFrequencyMutation: (
    billing_frequency: "monthly" | "quarterly" | "yearly"
  ) => void;
}

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
  createTagMutation: (variables: PlanType["tags"]) => void;
}
export const PlanSummary = ({
  plan,
  createTagMutation,
  createPlanExternalLink,
  deletePlanExternalLink,
}: PlanSummaryProps) => {
  const { plan_tags } = useGlobalStore((state) => state.org);
  const windowWidth = useMediaQuery();
  const inputRef = useRef<HTMLInputElement | null>(null!);
  return (
    <div className="min-h-[200px]  min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card  shadow-lg ">
      <Typography.Title className="pt-4 whitespace-pre-wrap" level={2}>
        Summary
      </Typography.Title>

      <div>
        <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
        <div className="flex items-center text-card-text justify-between gap-2 mb-1">
          <div className=" font-normal whitespace-nowrap leading-4">
            Plan ID
          </div>
          <div className="flex gap-1">
            {" "}
            <div className="!text-card-grey">
              {createShortenedText(plan.plan_id, windowWidth >= 2500)}
            </div>
            <CopyText showIcon onlyIcon textToCopy={plan.plan_id} />
          </div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">
            Total Active Subscriptions
          </div>
          <div className="!text-card-grey">{plan.active_subscriptions}</div>
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
                <PlansTags tags={plan_tags} />
              </DropdownComponent.Trigger>
              <DropdownComponent.Container>
                {plan_tags &&
                  plan_tags.map((tag, index) => (
                    <DropdownComponent.MenuItem
                      onSelect={() => {
                        //should actually serve as a delete
                      }}
                    >
                      <span key={index} className="flex gap-2 justify-between">
                        <span className="flex gap-2 ">
                          <Badge.Dot fill={tag.tag_hex} />
                          <span className="text-black">{tag.tag_name}</span>
                        </span>
                        <CheckCircleOutlined className="!text-gold" />
                      </span>
                    </DropdownComponent.MenuItem>
                  ))}
                <DropdownComponent.MenuItem
                  onSelect={() => {
                    const tags = [...plan.tags];
                    const newTag = createTags(inputRef.current!.value);
                    tags.push(newTag);
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
  // const schedule = (day: Number) => {
  //   if (day >= 1 && day <= 10) {
  //     return "Start of Month";
  //   } else if (day >= 11 && day <= 20) {
  //     return "Middle of Month";
  //   } else {
  //     return "End of Month";
  //   }
  // };

  return (
    <div className="min-h-[200px]  min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card  shadow-lg ">
      <Typography.Title className="pt-4 whitespace-pre-wrap grid gap-4 font-arimo !text-[18px] items-center grid-cols-1 md:grid-cols-2">
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
      <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
      <div className="grid  items-center grid-cols-1 md:grid-cols-2">
        <div className="w-[240px]">
          <div className="flex items-center text-card-text justify-between mb-1">
            <div className=" font-normal font-arimo whitespace-nowrap leading-4">
              Recurring Price
            </div>
            <div className="flex gap-1">
              {" "}
              <div className="text-gold">{`${plan.display_version.currency.symbol}${plan.display_version.flat_rate}`}</div>
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal font-arimo whitespace-nowrap leading-4">
              Plan Duration
            </div>
            <div className="!text-card-grey">
              {capitalize(plan.plan_duration)}
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal font-arimo whitespace-nowrap leading-4">
              Created At
            </div>
            <div className="!text-card-grey">
              {" "}
              {dayjs(version?.created_on).format("YYYY/MM/DD")}
            </div>
          </div>
        </div>

        <div className="w-[254px] ml-auto">
          <div className="flex items-center text-card-text justify-between gap-2 mb-1">
            <div className=" font-normal font-arimo whitespace-nowrap leading-4">
              Plan on next cycle
            </div>
            <div className="flex gap-1 ">
              {" "}
              <div className="!text-card-grey">
                {version?.transition_to
                  ? capitalize(version.transition_to)
                  : "Self"}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal font-arimo whitespace-nowrap leading-4">
              Recurring Bill Type
            </div>
            <div>
              {
                <Badge>
                  <Badge.Content>
                    <div className="p-1">
                      {constructBillType(
                        plan.display_version.flat_fee_billing_type
                      )}
                    </div>
                  </Badge.Content>
                </Badge>
              }
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-normal font-arimo whitespace-nowrap leading-4">
              Schedule
            </div>
            <div>
              {" "}
              <span>–</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
const PlanComponents: FC<PlanComponentsProps> = ({
  components,
  plan,
  updateBillingFrequencyMutation,
}) => {
  const selectRef = useRef<HTMLSelectElement | null>(null!);

  return (
    <div className="">
      {components && components.length > 0 ? (
        <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card  shadow-lg ">
          <Typography.Title className="pt-4 whitespace-pre-wrap font-arimo !text-[18px]">
            Added Components
          </Typography.Title>
          <div>
            <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
          </div>
          <div className="grid gap-6 grid-cols-1 xl:grid-cols-4">
            {components.map((component) => (
              <div className="pt-2 pb-4 bg-primary-50 mt-2  mb-2 p-4 min-h-[152px] min-w-[270px]">
                <div className="text-base text-card-text align-middle">
                  <div> {component.billable_metric.metric_name}</div>
                </div>
                <div>
                  <div className=" w-full h-[1.5px] mt-4 bg-card-divider mb-2" />
                  <Table
                    dataSource={component.tiers}
                    pagination={false}
                    showHeader={false}
                    bordered={false}
                    className="noborderTable"
                    size="middle"
                    columns={[
                      {
                        title: "Range",
                        dataIndex: "range_start",
                        key: "range_start",
                        align: "left",
                        width: "50%",
                        className: "bg-primary-50 pointer-events-none",
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
                        className:
                          "bg-primary-50 pointer-events-none !text-card-grey",
                        render: (value: any, record: any) => (
                          <div>
                            {renderCost(record, component.pricing_unit)}
                          </div>
                        ),
                      },
                    ]}
                  />
                </div>
              </div>
            ))}
          </div>
          {/* <div>
            <Select>
              <Select.Label className="after:content-['*'] after:ml-0.5 after:text-red-500">
                Billing Frequency
              </Select.Label>
              <Select.Select
                onChange={(e) => {
                  updateBillingFrequencyMutation(
                    e.target.value as "monthly" | "quarterly" | "yearly"
                  );
                }}
                ref={selectRef}
              >
                <Select.Option selected>{plan.plan_duration}</Select.Option>
                {["quarterly", "yearly"].map((el) => (
                  <Select.Option>{el}</Select.Option>
                ))}
              </Select.Select>
            </Select>
          </div> */}
        </div>
      ) : (
        <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card  shadow-lg ">
          <Typography.Title level={2}>Added Components</Typography.Title>
          <div className="w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
          <div className="text-card-grey text-base">No components added</div>
        </div>
      )}
    </div>
  );
};
export default PlanComponents;
