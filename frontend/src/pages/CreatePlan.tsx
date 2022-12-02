import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
} from "antd";
// @ts-ignore
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import UsageComponentForm from "../components/Plans/UsageComponentForm";
import { useMutation, useQueryClient } from "react-query";
import { toast } from "react-toastify";

import {
  CreateComponent,
  CreateInitialVersionType,
  CreatePlanType,
  InitialExternalLinks,
  PlanType,
} from "../types/plan-type";
import { Plan } from "../api/api";
import { FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import LinkExternalIds from "../components/Plans/LinkExternalIds";
import { PageLayout } from "../components/base/PageLayout";
import { ComponentDisplay } from "../components/Plans/ComponentDisplay";
import FeatureDisplay from "../components/Plans/FeatureDisplay";

interface ComponentDisplay {
  metric: string;
  cost_per_batch: number;
  metric_units_per_batch: number;
  free_metric_units: number;
  max_metric_units: number;
  id: number;
}

const durationConversion = {
  monthly: "Month",
  quarterly: "Quarter",
  yearly: "Year",
};

const CreatePlan = () => {
  const [componentVisible, setcomponentVisible] = useState<boolean>();
  const [allPlans, setAllPlans] = useState<PlanType[]>([]);
  const [featureVisible, setFeatureVisible] = useState<boolean>(false);
  const [priceAdjustmentType, setPriceAdjustmentType] =
    useState<string>("none");
  const navigate = useNavigate();
  const [componentsData, setComponentsData] = useState<CreateComponent[]>([]);
  const [form] = Form.useForm();
  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>([]);
  const [editComponentItem, setEditComponentsItem] =
    useState<CreateComponent>();
  const [availableBillingTypes, setAvailableBillingTypes] = useState<
    { name: string; label: string }[]
  >([
    { label: "Monthly", name: "monthly" },
    { label: "Quarterly", name: "quarterly" },
    { label: "Yearly", name: "yearly" },
  ]);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!allPlans?.length) {
      Plan.getPlans().then((data) => setAllPlans(data));
    }
  }, []);

  const mutation = useMutation(
    (post: CreatePlanType) => Plan.createPlan(post),
    {
      onSuccess: () => {
        toast.success("Successfully created Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
        queryClient.invalidateQueries(["plan_list"]);
        navigate("/plans");
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
      console.log(newComponentsData);
    }
    setEditComponentsItem(undefined);
    setcomponentVisible(false);
  };

  const handleComponentEdit = (id: any) => {
    const currentComponent = componentsData.filter((item) => item.id === id)[0];

    setEditComponentsItem(currentComponent);
    setcomponentVisible(true);
  };

  const deleteComponent = (id: number) => {
    setComponentsData(componentsData.filter((item) => item.id !== id));
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

  const setExternalLinks = (links: string[]) => {
    form.setFieldValue("initial_external_links", links);
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
              proration_granularity: components[i].proration_granularity,
            };
            usagecomponentslist.push(usagecomponent);
          }
        }

        if (values.usage_billing_frequency === "yearly") {
          values.usage_billing_frequency = "end_of_period";
        }

        const initialPlanVersion: CreateInitialVersionType = {
          description: values.description,
          flat_fee_billing_type: values.flat_fee_billing_type,
          transition_to_plan_id: values.transition_to_plan_id,
          flat_rate: values.flat_rate,
          components: usagecomponentslist,
          features: planFeatures,
          usage_billing_frequency: values.usage_billing_frequency,
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

        if (values.align_plan == "calendar_aligned") {
          if (values.plan_duration === "yearly") {
            initialPlanVersion["day_anchor"] = 1;
            initialPlanVersion["month_anchor"] = 1;
          }
          if (values.plan_duration === "monthly") {
            initialPlanVersion["day_anchor"] = 1;
          }
          if (values.plan_duration === "quarterly") {
            initialPlanVersion["day_anchor"] = 1;
            initialPlanVersion["month_anchor"] = 1;
          }
        }
        const plan: CreatePlanType = {
          plan_name: values.name,
          plan_duration: values.plan_duration,
          initial_version: initialPlanVersion,
        };

        const links = values.initial_external_links;
        if (links?.length) {
          plan.initial_external_links = links.map((link) => ({
            source: "stripe",
            external_plan_id: link,
          }));
        }
        mutation.mutate(plan);
      })
      .catch((info) => {});
  };

  return (
    <PageLayout
      title="Create Plan"
      onBack={goBackPage}
      extra={[
        <Button
          key="create"
          onClick={() => form.submit()}
          size="large"
          type="primary"
        >
          Create new plan
        </Button>,
      ]}
    >
      <Form.Provider>
        <Form
          form={form}
          name="create_plan"
          initialValues={{
            flat_rate: 0,
            flat_fee_billing_type: "in_advance",
            price_adjustment_type: "none",
            plan_duration: "monthly",
            align_plan: "calendar_aligned",
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
              <Row gutter={[24, 24]}>
                <Col span="24">
                  <Card title="Plan Information">
                    <Form.Item
                      label="Plan Name"
                      name="name"
                      rules={[
                        {
                          required: true,
                          message: "Please Name Your Plan",
                        },
                      ]}
                    >
                      <Input placeholder="Ex: Starter Plan" />
                    </Form.Item>
                    <Form.Item label="Description" name="description">
                      <Input
                        type="textarea"
                        placeholder="Ex: Cheapest plan for small scale businesses"
                      />
                    </Form.Item>
                    <Form.Item
                      label="Plan Duration"
                      name="plan_duration"
                      rules={[
                        {
                          required: true,
                          message: "Please select a duration",
                        },
                      ]}
                    >
                      <Radio.Group
                        onChange={(e) => {
                          if (e.target.value === "monthly") {
                            setAvailableBillingTypes([
                              { label: "Monthly", name: "monthly" },
                            ]);
                            form.setFieldValue(
                              "usage_billing_frequency",
                              "monthly"
                            );
                          } else if (e.target.value === "quarterly") {
                            setAvailableBillingTypes([
                              { label: "Monthly", name: "monthly" },
                              { label: "Quarterly", name: "quarterly" },
                            ]);
                            form.setFieldValue(
                              "usage_billing_frequency",
                              "quarterly"
                            );
                          } else {
                            setAvailableBillingTypes([
                              { label: "Monthly", name: "monthly" },
                              { label: "Quarterly", name: "quarterly" },
                              { label: "Yearly", name: "yearly" },
                            ]);
                            form.setFieldValue(
                              "usage_billing_frequency",
                              "yearly"
                            );
                          }
                        }}
                      >
                        <Radio value="monthly">Monthly</Radio>
                        <Radio value="quarterly">Quarterly</Radio>
                        <Radio value="yearly">Yearly</Radio>
                      </Radio.Group>
                    </Form.Item>
                    <Form.Item
                      label="When To Bill"
                      name="align_plan"
                      rules={[
                        {
                          required: true,
                          message: "Please Select One",
                        },
                      ]}
                    >
                      <Radio.Group>
                        <Radio value="calendar_aligned">
                          Start of Every{" "}
                          {
                            durationConversion[
                              form.getFieldValue("plan_duration")
                            ]
                          }
                        </Radio>
                        <Radio value="subscription_aligned">
                          Start of Subscription
                        </Radio>
                      </Radio.Group>
                    </Form.Item>

                    <Form.Item name="flat_rate" label="Base Cost">
                      <InputNumber
                        addonBefore="$"
                        defaultValue={0}
                        precision={2}
                      />
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
                          <Select.Option
                            key={plan.plan_id}
                            value={plan.plan_id}
                          >
                            {plan.plan_name}
                          </Select.Option>
                        ))}
                      </Select>
                    </Form.Item>
                    <Form.Item
                      name="initial_external_links"
                      label="Link External ids"
                    >
                      <LinkExternalIds
                        externalIds={[]}
                        setExternalLinks={setExternalLinks}
                      />
                    </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>

            <Col span={14}>
              <Card
                title="Added Components"
                className="h-full"
                style={{
                  borderRadius: "0.5rem",
                  borderWidth: "2px",
                  borderColor: "#EAEAEB",
                  borderStyle: "solid",
                }}
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
                <div className="absolute inset-x-0 bottom-0 justify-center">
                  <div className="w-full border-t border-gray-300 py-2" />
                  <div className="mx-4">
                    <Form.Item
                      label="Components Billing Frequency"
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
                      <Radio.Group>
                        {availableBillingTypes.map((type) => (
                          <Radio value={type.name}>{type.label}</Radio>
                        ))}
                      </Radio.Group>
                    </Form.Item>
                  </div>
                </div>
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
    </PageLayout>
  );
};

export default CreatePlan;
