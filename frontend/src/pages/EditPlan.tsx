import {
  Button,
  Select,
  Form,
  Card,
  Input,
  InputNumber,
  Row,
  Col,
  Radio,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import UsageComponentForm from "../components/Plans/UsageComponentForm";
import { useMutation, useQueryClient } from "react-query";
import { toast } from "react-toastify";

import {
  CreatePlanType,
  CreateComponent,
  PlanType,
  PlanDetailType,
  CreateInitialVersionType,
  CreatePlanVersionType,
} from "../types/plan-type";
import { Plan } from "../api/api";
import { FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { usePlanState, usePlanUpdater } from "../context/PlanContext";
// @ts-ignore
import React from "react";
import { PageLayout } from "../components/base/PageLayout";
import ComponentDisplay from "../components/Plans/ComponentDisplay";
import FeatureDisplay from "../components/Plans/FeatureDisplay";
import TargetCustomerForm from "../components/Plans/TargetCustomerForm";
import VersionActiveForm from "../components/Plans/VersionActiveForm";

interface CustomizedState {
  plan: PlanType;
}

interface Props {
  type: "backtest" | "version" | "custom";
  plan: PlanDetailType;
  versionIndex: number;
}

const EditPlan = ({ type, plan, versionIndex }: Props) => {
  const [componentVisible, setcomponentVisible] = useState<boolean>();
  const [featureVisible, setFeatureVisible] = useState<boolean>(false);
  const [targetCustomerFormVisible, setTargetCustomerFormVisible] =
    useState<boolean>(false);
  const [versionActiveFormVisible, setVersionActiveFormVisible] =
    useState<boolean>(false);
  const [activeVersion, setActiveVersion] = useState<boolean>(false);
  const [activeVersionType, setActiveVersionType] = useState<string>();
  const navigate = useNavigate();
  const [componentsData, setComponentsData] = useState<any>([]);
  const [form] = Form.useForm();
  const { setReplacementPlan } = usePlanUpdater();
  const [editComponentItem, setEditComponentsItem] = useState<any>();
  const [targetCustomerId, setTargetCustomerId] = useState<string>(); // target customer id
  const [allPlans, setAllPlans] = useState<PlanType[]>([]);
  const [availableBillingTypes, setAvailableBillingTypes] = useState<
    { name: string; label: string }[]
  >([
    { label: "Monthly", name: "monthly" },
    { label: "Quarterly", name: "quarterly" },
    { label: "Yearly", name: "yearly" },
  ]);
  const [priceAdjustmentType, setPriceAdjustmentType] = useState<string>(
    plan.versions[versionIndex].price_adjustment?.price_adjustment_type ??
      "none"
  );

  const queryClient = useQueryClient();

  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>(
    plan.versions[versionIndex].features
  );

  useEffect(() => {
    if (!allPlans?.length) {
      Plan.getPlans().then((data) => setAllPlans(data));
    }
  }, []);

  useEffect(() => {
    const initialComponents: any[] = plan.versions[versionIndex].components.map(
      (component) => {
        return {
          metric: component.billable_metric.billable_metric_name,
          tiers: component.tiers,
          separate_by: component.separate_by,
          proration_granularity: component.proration_granularity,
          id: component.billable_metric.billable_metric_name,
        };
      }
    );
    setComponentsData(initialComponents);
  }, [plan.versions[versionIndex].components]);

  const mutation = useMutation(
    (data: CreatePlanVersionType) => Plan.createVersion(data),
    {
      onSuccess: () => {
        toast.success("Successfully created new version", {
          position: toast.POSITION.TOP_CENTER,
        });
        queryClient.invalidateQueries(["plan_list"]);
        navigate("/plans/" + plan.plan_id);
      },
      onError: () => {
        toast.error("Failed to create version", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const createPlanMutation = useMutation(
    (post: CreatePlanType) => Plan.createPlan(post),
    {
      onSuccess: (res) => {
        queryClient.invalidateQueries(["plan_list"]);
        form.resetFields();
        if (type == "backtest") {
          setReplacementPlan(res);
          navigate("/create-experiment");
        }
        if (type == "custom") {
          navigate("/plans");
        }
      },
      onError: () => {
        toast.error("Failed to create Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const addFeatures = (newFeatures: FeatureType[]) => {
    for (let i = 0; i < newFeatures.length; i++) {
      if (
        planFeatures.some(
          (feat) => feat.feature_name === newFeatures[i].feature_name
        )
      ) {
      } else {
        setPlanFeatures((prev) => [...prev, newFeatures[i]]);
      }
    }
    setFeatureVisible(false);
  };

  const editFeatures = (feature_name: string) => {
    const currentFeature = planFeatures.filter(
      (item) => item.feature_name === feature_name
    )[0];
    setFeatureVisible(true);
  };

  const removeFeature = (feature_name: string) => {
    setPlanFeatures(
      planFeatures.filter((item) => item.feature_name !== feature_name)
    );
  };

  const onFinishFailed = (errorInfo: any) => {};

  const hideComponentModal = () => {
    setcomponentVisible(false);
  };

  const showComponentModal = () => {
    setcomponentVisible(true);
  };

  const hideTargetCustomerForm = () => {
    setTargetCustomerFormVisible(false);
  };

  const handleComponentAdd = (newData: any) => {
    const old = componentsData;

    if (editComponentItem) {
      const index = componentsData.findIndex(
        (item) => item.id === editComponentItem.id
      );
      old[index] = newData;
      setComponentsData(old);
    } else {
      const newComponentsData = [
        ...old,
        {
          ...newData,
          id: Math.floor(Math.random() * 1000),
        },
      ];
      setComponentsData(newComponentsData);
    }
    setEditComponentsItem(undefined);
    setcomponentVisible(false);
  };

  const handleComponentEdit = (name: string) => {
    const currentComponent = componentsData.filter(
      (item) => item.id === name
    )[0];

    setEditComponentsItem(currentComponent);
    setcomponentVisible(true);
  };

  const deleteComponent = (name: string) => {
    setComponentsData(componentsData.filter((item) => item.metric !== name));
  };
  const hideFeatureModal = () => {
    setFeatureVisible(false);
  };

  const showFeatureModal = () => {
    setFeatureVisible(true);
  };

  const goBackPage = () => {
    navigate(-1);
  };

  const onFinish = () => {
    form
      .validateFields()
      .then(() => {
        if (type === "custom") {
          setTargetCustomerFormVisible(true);
        } else if (type === "version") {
          setVersionActiveFormVisible(true);
        } else {
          form.submit();
        }
      })
      .catch((errorInfo) => {
        toast.error(errorInfo.errorFields[0].errors[0]);
      });
  };

  const completeCustomPlan = (target_customer_id: string) => {
    setTargetCustomerId(target_customer_id);
    form.submit();
  };

  const completeNewVersion = (active: boolean, active_type: string) => {
    setActiveVersion(active);
    if (active) {
      setActiveVersionType(active_type);
    }
    form.submit();
  };

  const submitPricingPlan = () => {
    form
      .validateFields()
      .then((values) => {
        const usagecomponentslist: CreateComponent[] = [];
        const components: any = Object.values(componentsData);
        if (components) {
          for (let i = 0; i < components.length; i++) {
            const usagecomponent: CreateComponent = {
              billable_metric_name: components[i].metric,
              tiers: components[i].tiers,
              separate_by: components[i].separate_by,
            };
            usagecomponentslist.push(usagecomponent);
          }
        }

        const initialPlanVersion: CreateInitialVersionType = {
          description: values.description,
          flat_fee_billing_type: values.flat_fee_billing_type,
          transition_to_plan_id: values.transition_to_plan_id,
          flat_rate: values.flat_rate,
          components: usagecomponentslist,
          features: planFeatures,
          // usage_billing_frequency: values.usage_billing_frequency,
        };
        if (
          values.price_adjustment_type !== undefined &&
          values.price_adjustment_type !== "none"
        ) {
          if (
            values.price_adjustment_type === "percentage" ||
            values.price_adjustment_type === "fixed"
          ) {
            values.price_adjustment_amount =
              Math.abs(values.price_adjustment_amount) * -1;
          }
          initialPlanVersion["price_adjustment"] = {
            price_adjustment_type: values.price_adjustment_type,
            price_adjustment_amount: values.price_adjustment_amount,
          };
        }

        const newPlan: CreatePlanType = {
          plan_name: values.name,
          plan_duration: values.plan_duration,
          initial_version: initialPlanVersion,
        };
        if (type === "backtest") {
          newPlan["status"] = "experimental";
          createPlanMutation.mutate(newPlan);
        } else if (type === "version") {
          const newVersion: CreatePlanVersionType = {
            plan_id: plan.plan_id,
            description: values.description,
            flat_fee_billing_type: values.flat_fee_billing_type,
            transition_to_plan_id: values.transition_to_plan_id,
            flat_rate: values.flat_rate,
            components: usagecomponentslist,
            features: planFeatures,
            // usage_billing_frequency: values.usage_billing_frequency,
            make_active: activeVersion,
            make_active_type: activeVersionType,
          };
          if (
            values.price_adjustment_type !== undefined &&
            values.price_adjustment_type !== "none"
          ) {
            newVersion["price_adjustment"] = {
              price_adjustment_type: values.price_adjustment_type,
              price_adjustment_amount: values.price_adjustment_amount,
            };
          }

          mutation.mutate(newVersion);
        } else if (type === "custom") {
          // target_id = await targetCustomerFormVisible(true);

          newPlan["parent_plan_id"] = plan.plan_id;
          newPlan["target_customer_id"] = targetCustomerId;
          createPlanMutation.mutate(newPlan);
        }
      })
      .catch((info) => {});
  };

  function returnPageTitle(): string {
    if (type === "backtest") {
      return "Backtest Plan";
    } else if (type === "version") {
      return "Create New Version:" + " " + plan.plan_name;
    } else {
      return "Create Custom Plan:" + " " + plan.plan_name;
    }
  }

  function returnSubmitButtonText(): string {
    if (type === "backtest") {
      return "Create new Plan";
    } else if (type === "version") {
      return "Publish version";
    } else {
      return "Create custom plan";
    }
  }

  return (
    <PageLayout
      title={returnPageTitle()}
      extra={[
        <Button
          key={"back"}
          onClick={goBackPage}
          icon={<ArrowLeftOutlined />}
          type="default"
          size="large"
        >
          Back
        </Button>,
        <Button
          key="create"
          onClick={() => onFinish()}
          className="bg-black text-white justify-self-end"
          size="large"
          type="primary"
        >
          {returnSubmitButtonText()}
        </Button>,
      ]}
    >
      <Form.Provider>
        <Form
          form={form}
          name="create_plan"
          initialValues={{
            name: plan.plan_name,
            description: plan.versions[versionIndex].description,
            flat_rate: plan.versions[versionIndex].flat_rate,
            pay_in_advance: plan.versions[versionIndex].flat_fee_billing_type,
            // usage_billing_frequency: plan.versions[versionIndex].usage_billing_frequency,
            plan_duration: plan.plan_duration,
            flat_fee_billing_type:
              plan.versions[versionIndex].flat_fee_billing_type,
            price_adjustment_amount:
              plan.versions[versionIndex].price_adjustment
                ?.price_adjustment_amount,
            price_adjustment_type:
              plan.versions[versionIndex].price_adjustment
                ?.price_adjustment_type || "none",
          }}
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign="left"
        >
          <Row gutter={[24, 24]}>
            <Col span={10}>
              <Card
                title="Plan Information"
                style={{
                  borderRadius: "0.5rem",
                  borderWidth: "2px",
                  borderColor: "#EAEAEB",
                  borderStyle: "solid",
                }}
              >
                <Form.Item label="Plan Name" name="name">
                  <Input
                    placeholder="Ex: Starter Plan"
                    disabled={type === "version" ? true : false}
                  />
                </Form.Item>
                <Form.Item label="Description" name="description">
                  <Input
                    disabled={type === "version" ? true : false}
                    type="textarea"
                    placeholder="Ex: Cheapest plan for small scale businesses"
                  />
                </Form.Item>
                <Form.Item label="Plan Duration" name="plan_duration">
                  <Radio.Group
                    disabled={type === "version" ? true : false}
                    onChange={(e) => {
                      if (e.target.value === "monthly") {
                        setAvailableBillingTypes([
                          { label: "Monthly", name: "monthly" },
                        ]);
                      } else if (e.target.value === "quarterly") {
                        setAvailableBillingTypes([
                          { label: "Monthly", name: "monthly" },
                          { label: "Quarterly", name: "quarterly" },
                        ]);
                      } else {
                        setAvailableBillingTypes([
                          { label: "Monthly", name: "monthly" },
                          { label: "Quarterly", name: "quarterly" },
                          { label: "Yearly", name: "yearly" },
                        ]);
                      }
                    }}
                  >
                    <Radio value="monthly">Monthly</Radio>
                    <Radio value="quarterly">Quarterly</Radio>
                    <Radio value="yearly">Yearly</Radio>
                  </Radio.Group>
                </Form.Item>

                <Form.Item name="flat_rate" label="Base Cost">
                  <InputNumber addonBefore="$" defaultValue={0} precision={2} />
                </Form.Item>
                <Form.Item
                  name="flat_fee_billing_type"
                  label="Recurring Billing Type"
                >
                  <Select>
                    <Select.Option value="in_advance">
                      Pay in advance
                    </Select.Option>
                    <Select.Option value="in_arrears">
                      Pay in arrears
                    </Select.Option>
                  </Select>
                </Form.Item>
                <Form.Item
                  name="transition_to_plan_id"
                  label="Plan on next cycle"
                >
                  <Select>
                    {allPlans.map((plan) => (
                      <Select.Option value={plan.plan_id}>
                        {plan.plan_name}
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>
              </Card>
            </Col>

            <Col span={14}>
              <Card
                title="Added Components"
                style={{
                  borderRadius: "0.5rem",
                  borderWidth: "2px",
                  borderColor: "#EAEAEB",
                  borderStyle: "solid",
                }}
                className="h-full"
                extra={[
                  <Button
                    htmlType="button"
                    onClick={() => showComponentModal()}
                  >
                    Add Component
                  </Button>,
                ]}
              >
                <Form.Item
                  wrapperCol={{ span: 24 }}
                  shouldUpdate={(prevValues, curValues) =>
                    prevValues.components !== curValues.components
                  }
                >
                  <ComponentDisplay
                    componentsData={componentsData}
                    handleComponentEdit={handleComponentEdit}
                    deleteComponent={deleteComponent}
                  />
                </Form.Item>
                {/* <div className="absolute inset-x-0 bottom-0 justify-center">
                  <div className="w-full border-t border-gray-300 py-2" />
                  <div className="mx-4">
                    <Form.Item
                      label="Usage Billing Frequency"
                      name="usage_billing_frequency"
                      shouldUpdate={(prevValues, currentValues) =>
                        prevValues.plan_duration !== currentValues.plan_duration
                      }
                      rules={[
                        {
                          required: true,
                          message: "Please select an interval",
                        },
                      ]}
                    >
                      <Radio.Group disabled={type === "version" ? true : false}>
                        {availableBillingTypes.map((type) => (
                          <Radio value={type.name}>{type.label}</Radio>
                        ))}
                      </Radio.Group>
                    </Form.Item>
                  </div>
                </div> */}
              </Card>
            </Col>
            <Col span="24">
              <Card
                className="w-full my-5"
                title="Added Features"
                style={{
                  borderRadius: "0.5rem",
                  borderWidth: "2px",
                  borderColor: "#EAEAEB",
                  borderStyle: "solid",
                }}
                extra={[
                  <Button htmlType="button" onClick={showFeatureModal}>
                    Add Feature
                  </Button>,
                ]}
              >
                <Form.Item
                  wrapperCol={{ span: 24 }}
                  shouldUpdate={(prevValues, curValues) =>
                    prevValues.components !== curValues.components
                  }
                >
                  <FeatureDisplay
                    planFeatures={planFeatures}
                    removeFeature={removeFeature}
                    editFeatures={editFeatures}
                  />
                </Form.Item>
              </Card>
            </Col>
            <Col span="24">
              <Card
                className="w-6/12 mb-20"
                title="Discount"
                style={{
                  borderRadius: "0.5rem",
                  borderWidth: "2px",
                  borderColor: "#EAEAEB",
                  borderStyle: "solid",
                }}
              >
                <div className="grid grid-cols-2">
                  <Form.Item
                    wrapperCol={{ span: 20 }}
                    label="Type"
                    name="price_adjustment_type"
                  >
                    <Select
                      onChange={(value) => {
                        setPriceAdjustmentType(value);
                      }}
                    >
                      <Select.Option value="none">None</Select.Option>
                      {/* <Select.Option value="price_override">
                        Overwrite Price
                      </Select.Option> */}
                      <Select.Option value="percentage">
                        Percentage Off
                      </Select.Option>
                      <Select.Option value="fixed">Flat Discount</Select.Option>
                    </Select>
                  </Form.Item>

                  {priceAdjustmentType !== "none" && (
                    <Form.Item
                      name="price_adjustment_amount"
                      wrapperCol={{ span: 24, offset: 4 }}
                      shouldUpdate={(prevValues, curValues) =>
                        prevValues.price_adjustment_type !==
                        curValues.price_adjustment_type
                      }
                      rules={[
                        {
                          required:
                            priceAdjustmentType !== undefined ||
                            priceAdjustmentType !== "none",
                          message: "Please enter a price adjustment value",
                        },
                      ]}
                    >
                      <InputNumber
                        addonAfter={
                          priceAdjustmentType === "percentage" ? "%" : null
                        }
                        addonBefore={
                          priceAdjustmentType === "fixed" ||
                          priceAdjustmentType === "price_override"
                            ? "$"
                            : null
                        }
                      />
                    </Form.Item>
                  )}
                </div>
              </Card>
            </Col>
          </Row>
        </Form>
        {componentVisible && (
          <UsageComponentForm
            visible={componentVisible}
            onCancel={hideComponentModal}
            componentsData={componentsData}
            handleComponentAdd={handleComponentAdd}
            editComponentItem={editComponentItem}
            setEditComponentsItem={setEditComponentsItem}
          />
        )}
        {featureVisible && (
          <FeatureForm
            visible={featureVisible}
            onCancel={hideFeatureModal}
            onAddFeatures={addFeatures}
          />
        )}
      </Form.Provider>
      {targetCustomerFormVisible && (
        <TargetCustomerForm
          visible={targetCustomerFormVisible}
          onCancel={hideTargetCustomerForm}
          onAddTargetCustomer={completeCustomPlan}
        />
      )}
      {versionActiveFormVisible && (
        <VersionActiveForm
          visible={versionActiveFormVisible}
          onCancel={() => setVersionActiveFormVisible(false)}
          onOk={completeNewVersion}
        />
      )}
    </PageLayout>
  );
};

export default EditPlan;
