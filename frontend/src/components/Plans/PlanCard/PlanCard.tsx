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
    <div className="planCard pointer" onClick={gotoPlanDetail}>
      <div className="absolute right-3" onClick={(e) => e.stopPropagation()}>
        <Dropdown overlay={planMenu} trigger={["click"]}>
          <Button type="text" size="small" onClick={(e) => e.preventDefault()}>
            <MoreOutlined />
          </Button>
        </Dropdown>
      </div>
      <Typography.Title className="pt-4" level={2}>
        {plan.plan_name}
      </Typography.Title>

      <div>
        {plan.parent_plan !== null ? (
          <Tag color="#C3986B">{plan.parent_plan?.plan_name}</Tag>
        ) : null}

        <div className="flex activeSubscriptions">
          <div className="pr-1">
            Total Active Subscriptions: {plan.active_subscriptions}
          </div>
        </div>

        <div className="planDetails">
          <div className="pr-1 planDetailsLabel">Plan ID:</div>
          <div className="planDetailsValue planIdOverflow font-menlo">
            {" "}
            {plan.plan_id}
          </div>
        </div>

        <div className="planDetails">
          <div className="pr-1 planDetailsLabel">Active Version:</div>
          <div className="planDetailsValue">
            {" "}
            {plan.display_version?.version}
          </div>
        </div>

        <div className="planDetails">
          <div className="pr-1 planDetailsLabel"># of versions:</div>
          <div className="planDetailsValue">{plan.num_versions}</div>
        </div>

        <div className="planDetails">
          <div className="pr-1 planDetailsLabel">Plan duration:</div>
          <div className="planDetailsValue"> {plan.plan_duration}</div>
        </div>
      </div>
    </div>
  );
};
export default PlanCard;
