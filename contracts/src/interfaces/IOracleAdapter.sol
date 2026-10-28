// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title IOracleAdapter
/// @notice Signed index values with a calendar revision window per index, explicit finalization and
///         void. Revised to docs/SPEC.md section 9 (plan 07-01). Signatures and NatSpec only.
/// @dev EIP-712 domain: name "wi-oracle", version "1", chainId, verifyingContract = this.
///      Report type string (exact):
///        Report(bytes32 indexId,uint32 day,int64 value,uint16 revision,uint64 asOf)
///      `vintageHash` is stored and emitted as audit metadata but is NOT part of the signed struct.
///      Windows (dayStart(D+1) = (day + 1) * 86400): fetchAt = dayStart(D+1) + fetchLag;
///      finalizeAt = fetchAt + disputeWindow; voidDay allowed from finalizeAt + voidGrace.
///      Values: int64 in the index scale (tenths of degF, hundredths of inch, or -1/0/1).
///      Settlement reads getFinal only.
interface IOracleAdapter {
    struct IndexConfig {
        uint32 fetchLag; // seconds after dayStart(D+1): CLI 12h, nClimGrid 4d12h, PRISM 6d12h
        uint32 disputeWindow; // v0 24h
        uint32 voidGrace; // v0 72h
        bool active;
    }

    struct Observation {
        int64 value;
        uint16 revision;
        uint64 asOf;
        bool posted;
        bool finalized;
        bool voided;
        bytes32 vintageHash;
    }

    event IndexRegistered(bytes32 indexed indexId, uint32 fetchLag, uint32 disputeWindow, uint32 voidGrace);
    event IndexActiveSet(bytes32 indexed indexId, bool active);
    event ReporterSet(address indexed reporter, bool allowed);
    event Posted(
        bytes32 indexed indexId, uint32 indexed day, int64 value, uint16 revision, uint64 asOf, address signer, bytes32 vintageHash
    );
    event Finalized(bytes32 indexed indexId, uint32 indexed day, int64 value);
    event Voided(bytes32 indexed indexId, uint32 indexed day);

    /// @notice Owner. Registers a new index; the windows of an existing index can never change
    ///         (a change is a new index version).
    function registerIndex(bytes32 indexId, IndexConfig calldata cfg) external;

    /// @notice Owner. Deactivating stops new markets on the index; existing index-days still settle.
    function setIndexActive(bytes32 indexId, bool active) external;

    function setReporter(address reporter, bool allowed) external;

    /// @notice Anyone relays a reporter-signed value. Reverts unless: index registered and active;
    ///         not finalized or voided; asOf >= fetchAt; asOf <= now; now - asOf <= maxReportAge;
    ///         now < finalizeAt; revision > last accepted revision (first post: any); signer is an
    ///         allow-listed reporter.
    function post(
        bytes32 indexId,
        uint32 day,
        int64 value,
        uint16 revision,
        uint64 asOf,
        bytes32 vintageHash,
        bytes calldata signature
    ) external;

    /// @notice Anyone, at/after finalizeAt, if something was posted. Locks the last accepted value.
    function finalize(bytes32 indexId, uint32 day) external;

    /// @notice Anyone, at/after finalizeAt + voidGrace, if nothing was posted.
    function voidDay(bytes32 indexId, uint32 day) external;

    /// @notice Final value; reverts unless finalized.
    function getFinal(bytes32 indexId, uint32 day) external view returns (int64 value);

    function isVoid(bytes32 indexId, uint32 day) external view returns (bool);

    function observation(bytes32 indexId, uint32 day) external view returns (Observation memory);

    function indexConfig(bytes32 indexId) external view returns (IndexConfig memory);

    function fetchAt(bytes32 indexId, uint32 day) external view returns (uint64);

    function finalizeAt(bytes32 indexId, uint32 day) external view returns (uint64);

    function reportDigest(bytes32 indexId, uint32 day, int64 value, uint16 revision, uint64 asOf)
        external
        view
        returns (bytes32);

    function maxReportAge() external view returns (uint64);
}
