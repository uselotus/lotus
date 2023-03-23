import React, { useState, useRef, FC } from "react";
import { QueryClient, useMutation } from "@tanstack/react-query";
import { toast } from "react-toastify";
import { Table, Typography, Modal, Button, InputNumber } from "antd";
import { Plan } from "../../../api/api";
import { AlertType, CreateAlertType } from "../../../types/alert-type";
import { Component, Tier } from "../../../types/plan-type";
import Select from "../../base/Select/Select";
import { CurrencyType } from "../../../types/pricing-unit-type";
import { components } from "../../../gen-types";

interface AddOnsComponentsProps {
  components?: components["schemas"]["AddOnDetail"]["versions"][0]["components"];
  plan: components["schemas"]["AddOnDetail"];
  refetch: VoidFunction;
  alerts?: AlertType[];
  plan_version_id?: string;
}
const findAlertForComponent = (
  component: Component,
  alerts: AlertType[] | undefined
): AlertType | undefined => {
  if (alerts === undefined) {
    return undefined;
  }
  return alerts.find(
    (alert) => alert.metric.metric_id === component.billable_metric.metric_id
  );
};

const renderCost = (record: Tier, pricing_unit: CurrencyType) => {
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
      return <span>Free</span>;
  }
};
const AddOnComponents: FC<AddOnsComponentsProps> = ({
  components,
  plan,
  refetch,
  alerts,
  plan_version_id,
}) => {
  const selectRef = useRef<HTMLSelectElement | null>(null!);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [alertThreshold, setAlertThreshold] = useState(0);
  const [isCreateAlert, setIsCreateAlert] = useState(true);
  const [currentComponent, setCurrentComponent] = useState<Component>();
  const [currentAlertId, setCurrentAlertId] = useState<string>();
  const [isInvalid, setIsInvalid] = useState(false);
  const queryClient = new QueryClient();
  const createAlertMutation = useMutation(
    (post: CreateAlertType) => Plan.createAlert(post),
    {
      onSuccess: () => {
        setIsModalVisible(false);

        setAlertThreshold(0);
        refetch();
        toast.success("Successfully created alert.");
        // window.location.reload(false);
      },
    }
  );

  const deleteAlertMutation = useMutation(
    (post: { usage_alert_id: string }) => Plan.deleteAlert(post),
    {
      onSuccess: () => {
        setIsModalVisible(false);

        refetch();
        // toast.success("Deleted alert");
      },
    }
  );

  const deleteAlert = (usage_alert_id: string) => {
    deleteAlertMutation.mutate({
      usage_alert_id,
    });
  };

  const showModal = () => {
    setIsModalVisible(true);
  };

  const handleDeleteAlert = () => {
    deleteAlertMutation.mutate({
      usage_alert_id: currentAlertId!,
    });
    queryClient.invalidateQueries(["addon_detail", plan.addon_id]);
  };

  const submitAlertModal = (component: Component, usage_alert_id?: string) => {
    if (typeof alertThreshold !== "number") {
      toast.error("Must input a number");
      return;
    }
    if (isCreateAlert) {
      createAlertMutation.mutate({
        plan_version_id,
        metric_id: component.billable_metric.metric_id,
        threshold: alertThreshold,
      });
    } else {
      if (usage_alert_id !== undefined) {
        deleteAlertMutation.mutate({
          usage_alert_id,
        });
      }
      createAlertMutation.mutate({
        plan_version_id,
        metric_id: component.billable_metric.metric_id,
        threshold: alertThreshold,
      });
    }
    queryClient.invalidateQueries(["addon_detail", plan.addon_id]);
  };

  return (
    <div className="">
      {components && components.length > 0 ? (
        <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card ">
          <Typography.Title className="pt-4 whitespace-pre-wrap !text-[18px]">
            Added Components
          </Typography.Title>
          <div>
            <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
          </div>
          <div className="grid gap-6 grid-cols-1 xl:grid-cols-4">
            {components.map((component, index) => (
              <div
                className="pt-2 pb-4 bg-primary-50 mt-2  mb-2 p-4 min-h-[152px] min-w-[270px]"
                // eslint-disable-next-line react/no-array-index-key
                key={index}
              >
                <div className="text-base text-card-text align-middle">
                  <div> {component.billable_metric.metric_name}</div>
                </div>
                <div>
                  <div className="w-full h-[1.5px] mt-4 bg-card-divider mb-2" />
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
                          "bg-primary-50 pointer-events-none !text-card-grey arr",
                        render: (value: any, record: any) => (
                          <div>
                            {renderCost(record, component.pricing_unit)}
                          </div>
                        ),
                      },
                    ]}
                  />
                </div>
                <div className=" w-full h-[1.5px] mt-4 bg-card-divider mb-2" />

                {/* <div className="mt-4 self-end">
                  <div
                    className="flex"
                    aria-hidden
                    onClick={() => {
                      if (component.billable_metric.metric_type !== "counter") {
                        toast.error("Only counter metrics can create alerts");
                      } else {
                        if (
                          findAlertForComponent(component, alerts) !== undefined
                        ) {
                          const alert = findAlertForComponent(
                            component,
                            alerts
                          );
                          setIsCreateAlert(false);
                          setAlertThreshold(alert?.threshold);
                          setCurrentAlertId(alert?.usage_alert_id);
                        } else {
                          setIsCreateAlert(true);
                        }
                        setCurrentComponent(component);
                        showModal();
                      }
                    }}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      width="24"
                      height="24"
                      className="mr-2"
                    >
                      <path fill="none" d="M0 0h24v24H0z" />
                      <path d="M20 17h2v2H2v-2h2v-7a8 8 0 1 1 16 0v7zm-2 0v-7a6 6 0 1 0-12 0v7h12zm-9 4h6v2H9v-2z" />
                    </svg>
                    {findAlertForComponent(component, alerts) !== undefined ? (
                      <p className="align-middle">
                        Reaches:{" "}
                        {findAlertForComponent(component, alerts).threshold}
                      </p>
                    ) : (
                      <p className=" text-small align-middle self-center">
                        Set Alert
                      </p>
                    )}
                  </div>
                </div> */}
              </div>
            ))}
            <Modal
              title="Set Alert"
              visible={isModalVisible}
              onCancel={() => setIsModalVisible(false)}
              footer={
                isCreateAlert
                  ? [
                      <Button
                        key="back"
                        onClick={() => setIsModalVisible(false)}
                      >
                        Cancel
                      </Button>,
                      <Button
                        key="submit"
                        type="primary"
                        disabled={
                          isInvalid ||
                          (import.meta as any).env.VITE_IS_DEMO === "true"
                        }
                        onClick={() => {
                          if (import.meta.env.VITE_IS_DEMO === "true") {
                            toast.error("Not available in demo mode");
                            return;
                          }
                          console.log(import.meta.env.VITE_IS_DEMO);
                          submitAlertModal(currentComponent);
                        }}
                      >
                        Create
                      </Button>,
                    ]
                  : [
                      <Button
                        key="delete"
                        className=" bg-red-600"
                        onClick={() => deleteAlert(currentAlertId)}
                      >
                        Delete
                      </Button>,
                      <Button
                        key="submit"
                        type="primary"
                        disabled={isInvalid}
                        onClick={() =>
                          submitAlertModal(currentComponent, currentAlertId)
                        }
                      >
                        Update
                      </Button>,
                    ]
              }
            >
              <div className="flex flex-col justify-center items-center gap-4">
                {currentComponent?.billable_metric.metric_name} reaches:{"  "}
                <InputNumber
                  type="number"
                  pattern="[0-9]+"
                  onChange={(value) => {
                    if (value && typeof value === "number") {
                      setAlertThreshold(value);
                      setIsInvalid(false);
                    }
                    if (value === null) {
                      setIsInvalid(true);
                    }
                  }}
                  value={alertThreshold}
                />
                {isInvalid && (
                  <div className="text-red-800">Please enter a number</div>
                )}
              </div>
            </Modal>
          </div>
          <div>
            <Select>
              <Select.Label className="">Billing Frequency</Select.Label>
              <Select.Select disabled className="!w-1/4" ref={selectRef}>
                <Select.Option selected>monthy</Select.Option>
                {["quarterly", "yearly"].map((el) => (
                  <Select.Option key={el}>{el}</Select.Option>
                ))}
              </Select.Select>
            </Select>
          </div>
        </div>
      ) : (
        <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card">
          <Typography.Title level={2}>Added Components</Typography.Title>
          <div className="w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
          <div className="text-card-grey text-base">No components added</div>
        </div>
      )}
    </div>
  );
};
export default AddOnComponents;
