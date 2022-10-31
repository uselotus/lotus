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
import { useLocation, useNavigate, useParams } from "react-router-dom";
import UsageComponentForm from "../components/Plans/UsageComponentForm";
import { useMutation, useQueryClient, useQuery } from "react-query";
import { toast } from "react-toastify";

import {
  CreatePlanType,
  CreateComponent,
  PlanType,
  UpdatePlanType,
  PlanDetailType,
  CreateInitialVersionType,
  CreatePlanVersionType,
} from "../types/plan-type";
import { Plan } from "../api/api";
import { FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import { ArrowLeftOutlined } from "@ant-design/icons";
import React from "react";
import { PageLayout } from "../components/base/PageLayout";
import { usePlanState, usePlanUpdater } from "../context/PlanContext";
import ComponentDisplay from "../components/Plans/ComponentDisplay";
import FeatureDisplay from "../components/Plans/FeatureDisplay";
import { planDetailPlaceholder } from "../placeholderData/planPlaceholder";

interface CustomizedState {
  plan: PlanType;
}

interface Props {
  type: "backtest" | "version" | "custom";
  plan: PlanDetailType;
}

const EditPlan = ({ type, plan }: Props) => {
  const [componentVisible, setcomponentVisible] = useState<boolean>();
  const [featureVisible, setFeatureVisible] = useState<boolean>(false);
  const [targetCustomerFormVisible, setTargetCustomerFormVisible] =
    useState<boolean>(false);
  const location = useLocation();
  const { replacementPlan } = usePlanState();
  const { setReplacementPlan } = usePlanUpdater();
  const navigate = useNavigate();
  const [componentsData, setComponentsData] = useState<any>([]);
  const [form] = Form.useForm();
  const [editComponentItem, setEditComponentsItem] = useState<any>();
  const [availableBillingTypes, setAvailableBillingTypes] = useState<
    { name: string; label: string }[]
  >([
    { label: "Monthly", name: "monthly" },
    { label: "Quarterly", name: "quarterly" },
    { label: "Yearly", name: "yearly" },
  ]);

  const { planId } = useParams();

  const queryClient = useQueryClient();

  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>(
    plan.versions[0].features
  );

  useEffect(() => {
    const initialComponents: any[] = plan.versions[0].components.map(
      (component) => {
        return {
          metric: component.billable_metric.billable_metric_name,
          cost_per_batch: component.cost_per_batch,
          metric_units_per_batch: component.metric_units_per_batch,
          free_metric_units: component.free_metric_units,
          max_metric_units: component.max_metric_units,
        };
      }
    );
    console.log(initialComponents);
    setComponentsData(initialComponents);
  }, [plan.versions[0].components]);

  const mutation = useMutation(
    (data: CreatePlanVersionType) => Plan.createVersion(data),
    {
      onSuccess: () => {
        toast.success("Successfully created new version", {
          position: toast.POSITION.TOP_CENTER,
        });
        queryClient.invalidateQueries(["plan_list"]);
        navigate("/plans");
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
        if (type == "backtest") {
          setReplacementPlan(res);
        }
        queryClient.invalidateQueries(["plan_list"]);
        form.resetFields();
        navigate("/create-experiment");
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
    setComponentsData(componentsData.filter((item) => item.id !== name));
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

  const setTargetCustomer = async (target_customer_id: string) => {
    hideTargetCustomerForm();
    return target_customer_id;
  };

  const submitPricingPlan = () => {
    form
      .validateFields()
      .then((values) => {
        const usagecomponentslist: CreateComponent[] = [];
        const components: any = Object.values(componentsData);
        console.log(components);
        if (components) {
          for (let i = 0; i < components.length; i++) {
            const usagecomponent: CreateComponent = {
              billable_metric_name: components[i].metric,
              cost_per_batch: components[i].cost_per_batch,
              metric_units_per_batch: components[i].metric_units_per_batch,
              free_metric_units: components[i].free_metric_units,
              max_metric_units: components[i].max_metric_units,
            };
            usagecomponentslist.push(usagecomponent);
          }
        }

        const initialPlanVersion: CreateInitialVersionType = {
          description: values.description,
          flat_fee_billing_type: values.flat_fee_billing_type,
          flat_rate: values.flat_rate,
          components: usagecomponentslist,
          features: planFeatures,
          usage_billing_frequency: values.usage_billing_frequency,
        };

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
            flat_rate: values.flat_rate,
            components: usagecomponentslist,
            features: planFeatures,
            usage_billing_frequency: values.usage_billing_frequency,
          };

          mutation.mutate(newVersion);
        } else if (type === "custom") {
          // target_id = await targetCustomerFormVisible(true);

          newPlan["parent_plan_id"] = plan.plan_id;
          newPlan["target_customer_id"] = "3242342";
          createPlanMutation.mutate(newPlan);
        }
      })
      .catch((info) => {
        console.log("Validate Failed:", info);
      });
  };

  function returnPageTitle(): string {
    if (type === "backtest") {
      return "Backtest Plan";
    } else if (type === "version") {
      return "Create New Version:" + " " + plan.plan_name;
    } else {
      return "Create Custom Plan" + " " + plan.plan_name;
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
          onClick={() => form.submit()}
          className="bg-black text-white justify-self-end"
          size="large"
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
            description: plan.description,
            flat_rate: plan.flat_rate,
            pay_in_advance: plan.pay_in_advance,
            billing_interval: plan.interval,
          }}
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign="left"
        >
          <Row gutter={24}>
            <Col span={12}>
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
                  </Card>
                </Col>
                <Col span="24">
                  <Card
                    title="Added Features"
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
              </Row>
            </Col>

            <Col span={12}>
              <Row gutter={[24, 24]}>
                <Col span={24}>
                  <Card
                    title="Added Components"
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
                  </Card>
                </Col>
              </Row>
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
      {/* {targetCustomerFormVisible && (
        <TargetCustomerForm
          visible={targetCustomerFormVisible}
          onCancel={hideTargetCustomerForm}
          onAddTargetCustomer={completeCustomPlan}
        />
      )} */}
    </PageLayout>
  );
};

export default EditPlan;
