// @ts-ignore
import React, {FC} from "react";
import {
    Menu,
    Dropdown,
    Button,
    Typography,
} from "antd";
import {DeleteOutlined, MoreOutlined} from "@ant-design/icons";
import {Link} from "react-router-dom";
import {PlanType} from "../../../types/plan-type";
import "./PlanCard.css"

interface PlanCardProps {
    plan: PlanType;
    deletePlan: (billing_plan_id: string) => void;
}

const PlanCard: FC<PlanCardProps> = ({plan, deletePlan}) => {

    const planMenu = <Menu onClick={value => console.log(value)}>
            <Menu.Item key="1">
                <div className="planMenuArchiveIcon">
                    <div><DeleteOutlined/></div>
                    <div className="archiveLabel">Archive</div>
                </div>
            </Menu.Item>
        </Menu>;

    return (
        <div className="planCard">
            <div className="absolute right-3">
                <Dropdown overlay={planMenu} trigger={["click"]}>
                    <Button
                        type="text"
                        size="small"
                        onClick={(e) => e.preventDefault()}
                    >
                        <MoreOutlined/>
                    </Button>
                </Dropdown>
            </div>
            <Typography.Title className="pt-4" level={2}>{plan.name}</Typography.Title>

            <div>
                <div className="flex activeSubscriptions">
                    <div className="pr-1"> Total Active Subscriptions:</div>
                    <div className="activeSubscriptionsCount"> {plan.active_subscriptions}</div>
                </div>

                <div className="planDetails">
                    <div className="pr-1 planDetailsLabel">Plan Id:</div>
                    <div className="planDetailsValue planIdOverflow"> {plan.billing_plan_id}</div>
                </div>

                <div className="planDetails">
                    <div className="pr-1 planDetailsLabel">Active Versions:</div>
                    <div className="planDetailsValue"> {plan.flat_rate}</div>
                </div>

                <div className="planDetails">
                    <div className="pr-1 planDetailsLabel"># of versions:</div>
                    <div className="planDetailsValue">{plan.currency}</div>
                </div>

                <div className="planDetails">
                    <div className="pr-1 planDetailsLabel">Plan duration:</div>
                    <div className="planDetailsValue"> {plan.currency}</div>
                </div>
            </div>
        </div>);

}
export default PlanCard;
