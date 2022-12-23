// @ts-ignore
import React, { FC } from "react";
import { Menu, Dropdown, Button, Typography, Tag } from "antd";
import { DeleteOutlined, MoreOutlined } from "@ant-design/icons";
import { PlanType, UpdatePlanType } from "../../../types/plan-type";
import "./PlanCard.css";
import { useMutation, useQueryClient } from "react-query";
import { Plan } from "../../../api/api";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import CopyText from "../../base/CopytoClipboard";
import createShortenedText from "./createShortenedText";
import capitalize from "./capitalize";
interface PlanCardProps {
  plan: PlanType;
}

const PlanCard: FC<PlanCardProps> = ({ plan }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const mutation = useMutation(
    (plan_id: string) =>
      Plan.updatePlan(plan_id, {
        plan_name: plan.plan_name,
        status: "archived",
      }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("plan_list");
        toast.success("Plan archived");
      },
    }
  );

  const planMenu = (
    <Menu>
      <Menu.Item
        key="1"
        onClick={() => mutation.mutate(plan.plan_id)}
        disabled={plan.active_subscriptions > 0}
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

  const gotoPlanDetail = () => {
    navigate("/plans/" + plan.plan_id);
  };

  const customerNameOrID = (target_customer: any | undefined) => {
    if (target_customer.customer_name) {
      return target_customer.customer_name;
    } else {
      return target_customer.customer_id;
    }
  };

  return (
    <div
      className="min-h-[200px]  w-[246px] p-8 cursor-pointer font-main rounded-sm bg-[#f9f9f9]"
      onClick={(e) => {
        if ((e.target as HTMLInputElement).nodeName === "DIV") gotoPlanDetail();
      }}
    >
      <div className="absolute right-3" onClick={(e) => e.stopPropagation()}>
        <Dropdown overlay={planMenu} trigger={["click"]}>
          <Button type="text" size="small" onClick={(e) => e.preventDefault()}>
            <MoreOutlined />
          </Button>
        </Dropdown>
      </div>
      <Typography.Title className="pt-4 whitespace-pre-wrap" level={3}>
        {plan.target_customer !== null
          ? plan.plan_name + ": " + customerNameOrID(plan.target_customer)
          : plan.plan_name}
      </Typography.Title>

      <div>
        {plan.parent_plan !== null ? (
          <Tag color="#C3986B">{plan.parent_plan?.plan_name}</Tag>
        ) : null}
        <div className="divide-y-2 divide-[#EAEAEB]">
          <div className="flex mb-2">
            <div className="pr-1 font-normal  not-italic whitespace-nowrap text-sm  leading-3 text-[#C3986B]">
              Total Active Subscriptions: {plan.active_subscriptions}
            </div>
          </div>

          <div className="flex items-center text-[#3c3a38] justify-between gap-6 mb-1">
            <div className=" font-normal whitespace-nowrap leading-4">
              Plan ID
            </div>
            <div className="flex gap-1">
              {" "}
              <div>{createShortenedText(plan.plan_id)}</div>
              <CopyText showIcon onlyIcon textToCopy={plan.plan_id} />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between text-[#3c3a38] gap-6 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">
            # of versions:
          </div>
          <div>{plan.num_versions}</div>
        </div>

        <div className="flex items-center justify-between text-[#3c3a38] gap-6 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">
            Active Versions
          </div>
          <div> v{plan.display_version?.version}</div>
        </div>

        <div className="flex items-center text-[#3c3a38] justify-between gap-6 mb-1">
          <div className="font-normal text-[#3c3a38] whitespace-nowrap leading-4xs">
            Plan duration:
          </div>
          <div> {capitalize(plan.plan_duration)}</div>
        </div>
      </div>
    </div>
  );
};
export default PlanCard;
