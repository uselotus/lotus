import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/Customers/CustomerTable";
import {
  CustomerPlus,
  CustomerTotal,
  CustomerType,
} from "../types/customer-type";
import { Customer } from "../api/api";
import { Button, Modal } from "antd";
import LoadingSpinner from "../components/LoadingSpinner";
import {
  useQuery,
  UseQueryResult,
  useQueryClient,
  useMutation,
} from "react-query";
import { PageLayout } from "../components/base/PageLayout";
import CreateCustomerForm, {
  CreateCustomerState,
} from "../components/Customers/CreateCustomerForm";
import { toast } from "react-toastify";
import { Importer, ImporterField } from "react-csv-importer";
import "react-csv-importer/dist/index.css";

const ViewCustomers: FC = () => {
  const queryClient = useQueryClient();
  const [visible, setVisible] = useState(false);
  const [visibleImport, setVisibleImport] = useState(false);

  const { data, isLoading }: UseQueryResult<CustomerPlus[]> = useQuery<
    CustomerPlus[]
  >(["customer_list"], () =>
    Customer.getCustomers().then((res) => {
      return res;
    })
  );
  const { data: customerTotals, isLoading: totalLoading } = useQuery<
    CustomerTotal[]
  >(["customer_totals"], () =>
    Customer.getCustomerTotals().then((res) => {
      return res;
    })
  );

  const mutation = useMutation(
    (post: CustomerType) => Customer.createCustomer(post),
    {
      onSuccess: () => {
        setVisible(false);
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_totals"]);
        toast.success("Customer created successfully", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
      onError: () => {
        toast.error("Error creating customer", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  //batch create customers
  const importCustomers = useMutation(
    (post: CustomerType) => Customer.createCustomer(post),
    {
      onSuccess: () => {
        setVisible(false);
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["customer_totals"]);
        toast.success("Customer created successfully", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const openCustomerModal = () => {
    setVisible(true);
  };

  const onCancel = () => {
    setVisible(false);
  };

  const onCancelImport = () => {
    setVisibleImport(false);
  };

  const onImport = () => {};

  const onSave = (state: CreateCustomerState) => {
    const customerInstance: CustomerType = {
      customer_id: state.customer_id,
      customer_name: state.name,
      email: state.email,
      payment_provider: state.payment_provider,
      payment_provider_id: state.payment_provider_id,
    };
    mutation.mutate(customerInstance);
    onCancel();
  };

  return (
    <PageLayout
      title="Customers"
      extra={[
        <Button type="primary" size="large" onClick={openCustomerModal}>
          Create Customer
        </Button>,
      ]}
    >
      <div>
        {isLoading || data === undefined ? (
          <LoadingSpinner />
        ) : (
          <CustomerTable customerArray={data} totals={customerTotals} />
        )}
        <Modal
          title="Import Customers"
          visible={visibleImport}
          onCancel={onCancelImport}
        >
          <Importer
            assumeNoHeaders={false} // optional, keeps "data has headers" checkbox off by default
            restartable={false} // optional, lets user choose to upload another file when import is complete
            onStart={({ file, preview, fields, columnFields }) => {
              // optional, invoked when user has mapped columns and started import
              // prepMyAppForIncomingData();
            }}
            processChunk={async (rows, { startIndex }) => {
              // required, may be called several times
              // receives a list of parsed objects based on defined fields and user column mapping;
              // (if this callback returns a promise, the widget will wait for it before parsing more data)
              for (var row of rows) {
                console.log(row);
              }
            }}
            onComplete={({ file, preview, fields, columnFields }) => {
              // optional, invoked right after import is done (but user did not dismiss/reset the widget yet)
              toast.success("Import complete", {
                position: toast.POSITION.TOP_CENTER,
              });
            }}
            onClose={({ file, preview, fields, columnFields }) => {
              // optional, if this is specified the user will see a "Finish" button after import is done,
              // which will call this when clicked
              onCancelImport();
            }}

            // CSV options passed directly to PapaParse if specified:
            // delimiter={...}
            // newline={...}
            // quoteChar={...}
            // escapeChar={...}
            // comments={...}
            // skipEmptyLines={...}
            // delimitersToGuess={...}
            // chunkSize={...} // defaults to 10000
            // encoding={...} // defaults to utf-8, see FileReader API
          >
            <ImporterField name="customer_id" label="customer_id" />
            <ImporterField name="email" label="email" />
            <ImporterField name="stripe_id" label="stripe_id" optional />
          </Importer>
        </Modal>
        <CreateCustomerForm
          visible={visible}
          onSave={onSave}
          onCancel={onCancel}
        />
      </div>
    </PageLayout>
  );
};

export default ViewCustomers;
