import React, { FC } from "react";
import { PlanType } from "../types/plan-type";
import {
  Card,
  Menu,
  Dropdown,
  List,
  Statistic,
  Descriptions,
  Button,
  Col,
  Row,
  Space,
  Typography,
} from "antd";
import { Plan } from "../api/api";
import { ArrowDownOutlined, MoreOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { Components } from "antd/lib/date-picker/generatePicker";
import { Paper } from "./base/Paper";
import { Title } from "./base/Typograpy/index.";

function PlanDisplayBasic(props: {
  plan: PlanType;
  deletePlan: (billing_plan_id: string) => void;
}) {
  const planMenu = (
    <Menu>
      <Menu.Item key="0" disabled={props.plan.active_subscriptions !== 0}>
        <Link to="/update-plan" state={{ data: { plan: props.plan } }}>
          Edit
        </Link>
      </Menu.Item>
      <Menu.Item key="1" disabled={props.plan.active_subscriptions !== 0}>
        <a
          href="#"
          onClick={() => props.deletePlan(props.plan.billing_plan_id)}
        >
          Delete
        </a>
      </Menu.Item>
    </Menu>
  );

  const componentMenu = (
    <Menu>
      {props.plan.components.map((component) => (
        <Menu.Item key={component.id} className="border-2 bg-white">
          <List.Item.Meta
            style={{ width: "300px" }}
            title={
              <a href="#">{component.billable_metric.billable_metric_name}</a>
            }
            description={
              component.cost_per_batch
                ? `$${component.cost_per_batch} / ${component.metric_units_per_batch} Unit(s)`
                : "Free"
            }
          />
        </Menu.Item>
      ))}
    </Menu>
  );

  const featureMenue = (
    <Menu>
      {props.plan.features.map((feature) => (
        <Menu.Item key={feature.feature_name}>{feature.feature_name}</Menu.Item>
      ))}
    </Menu>
  );

  return (
    <Paper>
      <Descriptions
        title={props.plan.name}
        extra={
          <Dropdown overlay={planMenu} trigger={["click"]}>
            <Button
              type="text"
              size="small"
              onClick={(e) => e.preventDefault()}
            >
              <MoreOutlined />
            </Button>
          </Dropdown>
        }
      />

      <Row justify="center" align="middle">
        <Col span={11}>
          <p className="p-0 m-0">{props.plan.description}</p>
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="Plan ID" span={2}>
              {props.plan.billing_plan_id}
            </Descriptions.Item>
            <Descriptions.Item label="Interval">
              {props.plan.interval}
            </Descriptions.Item>
            <Descriptions.Item label="Recurring Price">
              {/* // use curreny formatter */}${props.plan.flat_rate}
            </Descriptions.Item>
            <Descriptions.Item label="Date Created">
              {props.plan.time_created}
            </Descriptions.Item>
            <Descriptions.Item label="Pay In Advance">Yes</Descriptions.Item>
          </Descriptions>
        </Col>

        <Col span={9}>
          <Space>
            <Dropdown overlay={componentMenu}>
              <Button style={{ width: 157 }}>
                Components: {props.plan.components.length} <ArrowDownOutlined />
              </Button>
            </Dropdown>
            <Dropdown overlay={featureMenue}>
              <Button className="bg-[#CCA43B69]" style={{ width: 157 }}>
                Features: {props.plan.features.length} <ArrowDownOutlined />
              </Button>
            </Dropdown>
          </Space>
        </Col>

        <Col span={4}>
          <div className="justify-self-center self-center text-center">
            <h1 className="font-main font-bold text-4xl">
              {props.plan.active_subscriptions}
            </h1>
            <h3>Active Subscriptions</h3>
          </div>
        </Col>
      </Row>
    </Paper>
  );
}

export default PlanDisplayBasic;
