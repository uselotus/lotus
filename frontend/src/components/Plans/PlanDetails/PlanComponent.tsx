// @ts-ignore
import React, { FC, useState } from "react";
import "./PlanDetails.css";
import { InputNumber, Table, Modal } from "antd";
import { Component, Tier } from "../../../types/plan-type";
import { PricingUnit } from "../../../types/pricing-unit-type";
import { useMutation, QueryClient } from "react-query";
import { Plan } from "../../../api/api";
import { AlertType, CreateAlertType } from "../../../types/alert-type";

interface PlanComponentsProps {
  components?: Component[];
  alerts?: AlertType[];
  plan_version_id: string;
}

const findAlertForComponent = (
  component: Component,
  alerts: AlertType[] | undefined
): AlertType | undefined => {
  if (alerts === undefined) {
    return undefined;
  }
  return alerts.find((alert) => {
    return alert.metric.metric_id === component.billable_metric.metric_id;
  });
};

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

const PlanComponents: FC<PlanComponentsProps> = ({
  components,
  alerts,
  plan_version_id,
}) => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [alertThreshold, setAlertThreshold] = useState(0);
  const [isCreateAlert, setIsCreateAlert] = useState(true);
  const [currentComponent, setCurrentComponent] = useState<Component>();

  const queryClient = new QueryClient();

  const createAlertMutation = useMutation(
    (post: CreateAlertType) => Plan.createAlert(post),
    {
      onSuccess: () => {
        setIsModalVisible(false);
        queryClient.invalidateQueries("plan_details");
        setAlertThreshold(0);
      },
    }
  );

  const deleteAlertMutation = useMutation(
    (post: { usage_alert_id: string }) => Plan.deleteAlert(post),
    {
      onSuccess: () => {
        setIsModalVisible(false);
        queryClient.invalidateQueries("plan_details");
      },
    }
  );

  const showModal = () => {
    setIsModalVisible(true);
  };

  const handleDeleteAlert = (usage_alert_id) => {
    deleteAlertMutation.mutate({
      usage_alert_id: usage_alert_id,
    });
  };

  const submitAlertModal = (component: Component, usage_alert_id?: string) => {
    if (isCreateAlert) {
      createAlertMutation.mutate({
        plan_version_id: "s",
        metric_id: "Test",
        threshold: alertThreshold,
      });
    } else {
      deleteAlertMutation.mutate({
        usage_alert_id: "2",
      });
      createAlertMutation.mutate({
        plan_version_id: "s",
        metric_id: "Test",
        threshold: alertThreshold,
      });
    }
  };

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
              <div>
                <div
                  className="flex hover:bg-background hover:bg-opacity-30"
                  onClick={() => {
                    findAlertForComponent(component, alerts) !== undefined
                      ? setIsCreateAlert(false)
                      : setIsCreateAlert(true);
                    showModal();
                  }}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    width="24"
                    height="24"
                  >
                    <path fill="none" d="M0 0h24v24H0z" />
                    <path d="M20 17h2v2H2v-2h2v-7a8 8 0 1 1 16 0v7zm-2 0v-7a6 6 0 1 0-12 0v7h12zm-9 4h6v2H9v-2z" />
                  </svg>
                  {findAlertForComponent(component, alerts) !== undefined ? (
                    <p>
                      Reaches{" "}
                      {findAlertForComponent(component, alerts).threshold}
                    </p>
                  ) : (
                    <p className=" text-small text-g">Set Alert</p>
                  )}
                </div>
              </div>
              <Modal
                title="Set Alert"
                visible={isModalVisible}
                onOk={() => submitAlertModal(component)}
                okText={isCreateAlert ? "Create" : "Update"}
                onCancel={() => setIsModalVisible(false)}
              >
                <div>
                  <div> {component.billable_metric.metric_name}</div> reaches{" "}
                  <InputNumber
                    min={0}
                    defaultValue={0}
                    onChange={(value) => {
                      if (value) {
                        setAlertThreshold(value);
                      }
                    }}
                    value={alertThreshold}
                  />
                </div>
              </Modal>
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
